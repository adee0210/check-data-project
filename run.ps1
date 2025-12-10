# PowerShell script để chạy hệ thống giám sát dữ liệu trên Windows

$SCRIPT_DIR = Split-Path -Parent $MyInvocation.MyCommand.Path
$PID_FILE = Join-Path $SCRIPT_DIR "check_data.pid"
$LOG_DIR = Join-Path $SCRIPT_DIR "logs"
$LOG_FILE = Join-Path $LOG_DIR "main.log"
$PYTHON_EXE = Join-Path $SCRIPT_DIR ".venv\Scripts\python.exe"
$MAIN_PY = Join-Path $SCRIPT_DIR "src\main.py"

# Tạo thư mục logs nếu chưa có
if (-not (Test-Path $LOG_DIR)) {
    New-Item -ItemType Directory -Path $LOG_DIR | Out-Null
}

function Start-Monitoring {
    # Kiểm tra xem đã chạy chưa
    if (Test-Path $PID_FILE) {
        $ProcessId = Get-Content $PID_FILE
        $Process = Get-Process -Id $ProcessId -ErrorAction SilentlyContinue
        if ($Process) {
            Write-Host "Hệ thống giám sát dữ liệu đang chạy (PID: $ProcessId)" -ForegroundColor Yellow
            return
        }
        else {
            Write-Host "Xóa file PID cũ..." -ForegroundColor Gray
            Remove-Item $PID_FILE
        }
    }

    Write-Host "Đang khởi động hệ thống giám sát dữ liệu..." -ForegroundColor Green
    Write-Host "File log: $LOG_FILE" -ForegroundColor Cyan
    
    # Chạy Python script ẩn (không hiện cửa sổ)
    $ProcessInfo = New-Object System.Diagnostics.ProcessStartInfo
    $ProcessInfo.FileName = $PYTHON_EXE
    $ProcessInfo.Arguments = $MAIN_PY
    $ProcessInfo.WorkingDirectory = $SCRIPT_DIR
    $ProcessInfo.UseShellExecute = $false
    $ProcessInfo.CreateNoWindow = $true  # Chạy ngầm không hiện cửa sổ
    $ProcessInfo.RedirectStandardOutput = $true
    $ProcessInfo.RedirectStandardError = $true
    
    $Process = New-Object System.Diagnostics.Process
    $Process.StartInfo = $ProcessInfo
    
    # Redirect output và error đến log file
    $Process.Start() | Out-Null
    
    # Lưu PID
    $Process.Id | Out-File $PID_FILE
    
    Write-Host "Hệ thống đã khởi động thành công (PID: $($Process.Id))" -ForegroundColor Green
    Write-Host "Sử dụng lệnh 'Get-Content $LOG_FILE -Wait' để xem log theo thời gian thực" -ForegroundColor Cyan
    Write-Host "Hoặc dùng './run.ps1 logs' để xem log" -ForegroundColor Cyan
}

function Stop-Monitoring {
    if (-not (Test-Path $PID_FILE)) {
        Write-Host "Không tìm thấy file PID. Hệ thống có đang chạy không?" -ForegroundColor Yellow
        return
    }

    $ProcessId = Get-Content $PID_FILE
    $Process = Get-Process -Id $ProcessId -ErrorAction SilentlyContinue
    
    if ($Process) {
        Write-Host "Đang dừng hệ thống giám sát dữ liệu (PID: $ProcessId)..." -ForegroundColor Yellow
        Stop-Process -Id $ProcessId -Force
        Start-Sleep -Seconds 2
        Remove-Item $PID_FILE
        Write-Host "Đã dừng hệ thống giám sát dữ liệu" -ForegroundColor Green
    }
    else {
        Write-Host "Không tìm thấy tiến trình với PID: $ProcessId" -ForegroundColor Red
        Remove-Item $PID_FILE
    }
}

function Restart-Monitoring {
    Write-Host "Đang khởi động lại hệ thống giám sát dữ liệu..." -ForegroundColor Cyan
    Stop-Monitoring
    Start-Sleep -Seconds 2
    Start-Monitoring
}

function Show-Status {
    if (Test-Path $PID_FILE) {
        $ProcessId = Get-Content $PID_FILE
        $Process = Get-Process -Id $ProcessId -ErrorAction SilentlyContinue
        
        if ($Process) {
            Write-Host "Trạng thái: ĐANG CHẠY" -ForegroundColor Green
            Write-Host "PID: $ProcessId"
            Write-Host "CPU: $($Process.CPU)"
            Write-Host "Memory: $([math]::Round($Process.WorkingSet64 / 1MB, 2)) MB"
            Write-Host "Start Time: $($Process.StartTime)"
            Write-Host "Log file: $LOG_FILE"
        }
        else {
            Write-Host "Trạng thái: DỪNG (PID file tồn tại nhưng tiến trình không chạy)" -ForegroundColor Red
        }
    }
    else {
        Write-Host "Trạng thái: DỪNG" -ForegroundColor Red
    }
}

function Show-Logs {
    if (Test-Path $LOG_FILE) {
        Write-Host "Đang hiển thị log (nhấn Ctrl+C để thoát)..." -ForegroundColor Cyan
        Get-Content $LOG_FILE -Wait -Tail 50
    }
    else {
        Write-Host "Không tìm thấy file log: $LOG_FILE" -ForegroundColor Red
    }
}

function Show-Help {
    Write-Host @"
Sử dụng: .\run.ps1 [command]

Commands:
  start      Khởi động hệ thống giám sát
  stop       Dừng hệ thống giám sát
  restart    Khởi động lại hệ thống
  status     Xem trạng thái hệ thống
  logs       Xem log theo thời gian thực
  help       Hiển thị trợ giúp này

Ví dụ:
  .\run.ps1 start      # Khởi động hệ thống
  .\run.ps1 status     # Kiểm tra trạng thái
  .\run.ps1 logs       # Xem log
  .\run.ps1 stop       # Dừng hệ thống

"@ -ForegroundColor Cyan
}

# Main script logic
switch ($args[0]) {
    "start" { Start-Monitoring }
    "stop" { Stop-Monitoring }
    "restart" { Restart-Monitoring }
    "status" { Show-Status }
    "logs" { Show-Logs }
    "help" { Show-Help }
    default {
        if ($args.Count -eq 0) {
            Show-Help
        }
        else {
            Write-Host "Lệnh không hợp lệ: $($args[0])" -ForegroundColor Red
            Write-Host "Sử dụng '.\run.ps1 help' để xem danh sách lệnh" -ForegroundColor Yellow
        }
    }
}
