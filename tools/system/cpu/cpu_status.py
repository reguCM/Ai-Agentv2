import subprocess

def cpu_status():
    result = subprocess.run([
        'powershell',
        '-NoProfile',
        '-NonInteractive',
        '-Command',
        'Get-CimInstance -ClassName Win32_Processor | Select LoadPercentage'
    ],
    capture_output=True,
    text=True
    )
    if result.returncode == 0:
        lines = result.stdout.strip().split('\n')
        status_value = lines[-1].strip() if lines else '0'
        return {'status': status_value}
    return {'status': 'error'}
