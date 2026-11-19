"""Watch only the Blender child we create. Global GPU totals are not per-process VRAM."""
import argparse
import csv
import json
import os
import shutil
import subprocess
import sys
import time
from pathlib import Path
import psutil

HERE = Path(__file__).resolve().parent
BLENDER = Path(os.environ.get('BLENDER_BIN') or shutil.which('blender') or 'C:/Program Files/Blender Foundation/Blender 5.3/blender.exe')
parser = argparse.ArgumentParser()
parser.add_argument('--timeout', type=int, default=300)
parser.add_argument('--reserve-gib', type=float, default=2.0)
parser.add_argument('--rss-limit-gib', type=float, default=20.5)
args, worker_args = parser.parse_known_args()
if '--tag' not in worker_args:
    raise SystemExit('--tag is required')
tag = worker_args[worker_args.index('--tag')+1]
for proc in psutil.process_iter(['pid', 'name']):
    if (proc.info['name'] or '').lower() == 'blender.exe':
        raise SystemExit(f'Refusing concurrent Blender process {proc.pid}; close it first')
if psutil.virtual_memory().available < 10*2**30:
    raise SystemExit('Less than 10 GiB RAM available before job; refusing stress test')
command = [str(BLENDER), '-b', '--factory-startup', '--debug-cycles', '--python-exit-code', '2',
           '--python', str(HERE / 'scene_worker.py'), '--', *worker_args, '--cycles-print-stats']
started = time.monotonic()
trace = []
reason = None
low_count = 0
with (HERE / (tag + '.log')).open('w', encoding='utf-8') as log:
    child = subprocess.Popen(command, stdout=log, stderr=subprocess.STDOUT,
                             env={**os.environ, 'PYTHONUNBUFFERED': '1'})
    process = psutil.Process(child.pid)
    while child.poll() is None:
        rss = 0
        private = 0
        try:
            mem = process.memory_info()
            rss = mem.rss
            private = getattr(mem, 'private', 0)
        except psutil.NoSuchProcess:
            pass
        system = psutil.virtual_memory()
        entry = {'elapsed_s': round(time.monotonic()-started, 3), 'rss_mib': round(rss/2**20, 2),
                 'private_mib': round(private/2**20, 2), 'available_ram_mib': round(system.available/2**20, 2)}
        try:
            gpu = subprocess.run(['nvidia-smi', '--query-gpu=memory.used,memory.free,utilization.gpu,temperature.gpu',
                                  '--format=csv,noheader,nounits'], capture_output=True, text=True, timeout=5,
                                 creationflags=getattr(subprocess, 'CREATE_NO_WINDOW', 0))
            values = next(csv.reader(gpu.stdout.strip().splitlines()))
            for key, value in zip(('gpu_global_used_mib', 'gpu_global_free_mib', 'gpu_util_pct', 'gpu_temp_c'), values):
                entry[key] = float(value.strip())
        except Exception as exc:
            entry['gpu_query_error'] = type(exc).__name__
        trace.append(entry)
        (HERE / (tag + '_telemetry.json')).write_text(json.dumps(trace), encoding='utf-8')
        low_count = low_count + 1 if system.available < args.reserve_gib * 2**30 else 0
        if low_count >= 2:
            reason = 'watchdog_system_ram_reserve'
        elif rss > args.rss_limit_gib * 2**30:
            reason = 'watchdog_child_rss_limit'
        elif time.monotonic()-started > args.timeout:
            reason = 'watchdog_timeout'
        elif entry.get('gpu_temp_c', 0) >= 88:
            reason = 'watchdog_gpu_temperature'
        if reason:
            for descendant in process.children(recursive=True):
                descendant.kill()
            if child.poll() is None:
                child.kill()
            break
        time.sleep(.5)
    exit_code = child.wait(timeout=15)
worker_file = HERE / (tag + '.json')
worker = json.loads(worker_file.read_text(encoding='utf-8')) if worker_file.exists() else {}
text = (HERE / (tag + '.log')).read_text(encoding='utf-8', errors='replace')
evidence = [line for line in text.splitlines() if any(term in line.lower() for term in
            ('out of memory', 'out of gpu memory', 'cuda_error_out_of_memory', 'failed to allocate', 'mapped host memory'))]
summary = {'tag': tag, 'command': command, 'exit_code': exit_code, 'watchdog_reason': reason,
           'wall_seconds': round(time.monotonic()-started, 3), 'worker': worker,
           'peak_rss_mib': max((x['rss_mib'] for x in trace), default=None),
           'peak_private_mib': max((x['private_mib'] for x in trace), default=None),
           'peak_global_gpu_mib': max((x.get('gpu_global_used_mib', 0) for x in trace), default=None),
           'initial_global_gpu_mib': trace[0].get('gpu_global_used_mib') if trace else None,
           'minimum_available_ram_mib': min((x['available_ram_mib'] for x in trace), default=None),
           'memory_log_evidence': evidence,
           'note': 'Global nvidia-smi VRAM includes Windows/apps; not per-process WDDM memory. Watchdog abort is NOT GPU OOM.'}
if worker.get('status') == 'render_completed':
    from PIL import Image, ImageStat
    with Image.open(worker['output']) as image:
        rgba = image.convert('RGBA')
        stats = ImageStat.Stat(rgba)
        extrema = rgba.getextrema()
        summary['image_validation'] = {'mean_rgba': stats.mean, 'extrema_rgba': extrema,
                                       'nonblank': extrema[3][1] > 0 and any(hi > lo for lo, hi in extrema[:3])}
(HERE / (tag + '_summary.json')).write_text(json.dumps(summary, indent=2), encoding='utf-8')
print(json.dumps(summary, indent=2))
if reason:
    print('WATCHDOG STOP: not evidence of GPU allocation failure')
if exit_code != 0 and not reason:
    print('LOG TAIL:', '\n'.join(text.splitlines()[-22:]))
# Job outcome is data, not the supervisor's exit status. Caller must inspect the summary.
