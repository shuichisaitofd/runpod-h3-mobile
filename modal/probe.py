# Modal probe: look inside the H3 long-video image (CPU only, no GPU) before building the real Modal app.
import modal

IMAGE = "ghcr.io/shuichisaitofd/runpod-h3-mobile:h3-longtest-c9443c9e535d3053ec858f602daa50af59c65e0d"
img = modal.Image.from_registry(IMAGE).entrypoint([]).run_commands("ln -sf \"$(command -v python3.12)\" /usr/local/bin/python && python --version")
app = modal.App("h3-probe", image=img)

CMD = r"""
echo '### start.sh'; sed -n 1,400p /start.sh
echo '### opt'; ls -la /opt; ls -la /opt/comfyui-baked | head -40
echo '### venvs'; ls -d /opt/*venv* /opt/comfyui-baked/.venv* 2>&1; ls /opt/comfyui-baked/.venv-cu128/bin 2>&1 | head
echo '### python'; which python python3 python3.12; python3.12 -c "import torch,sys;print(sys.version, torch.__version__)"
echo '### ffmpeg'; which ffmpeg
echo '### disk'; df -h / /tmp 2>&1
echo '### h3 workflows'; ls /opt/comfyui-baked/custom_nodes/ComfyUI-H3-Mobile/api_workflows
echo '### nproc'; nproc; free -g | head -2
"""

@app.function(timeout=600, cpu=2)
def probe():
    import subprocess
    r = subprocess.run(["bash", "-c", CMD], capture_output=True, text=True)
    return (r.stdout + "\nERR:\n" + r.stderr)[-30000:]

@app.local_entrypoint()
def main():
    out = probe.remote()
    open("probe_out.txt", "w").write(out)
    print(out)
