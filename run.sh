#!/bin/bash

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PID_FILE="$SCRIPT_DIR/check_data.pid"
LOG_DIR="$SCRIPT_DIR/logs"
LOG_FILE="$LOG_DIR/main.log"

mkdir -p "$LOG_DIR"

PYTHON_CMD="$SCRIPT_DIR/.venv/bin/python $SCRIPT_DIR/src/main.py"

start() {
    if [ -f "$PID_FILE" ]; then
        PID=$(cat "$PID_FILE")
        if ps -p "$PID" > /dev/null 2>&1; then
            echo "Hệ thống giám sát dữ liệu đang chạy (PID: $PID)"
            return 1
        else
            echo "Xóa file PID cũ..."
            rm "$PID_FILE"
        fi
    fi

    echo "Đang khởi động hệ thống giám sát dữ liệu..."
    echo "File log: $LOG_DIR/"
    cd "$SCRIPT_DIR"
    nohup $PYTHON_CMD &
    echo $! > "$PID_FILE"
    echo "Hệ thống đã khởi động thành công (PID: $(cat "$PID_FILE"))"
    echo "Sử dụng lệnh 'tail -f $LOG_DIR/api.log' để xem log API"
    echo "Hoặc 'tail -f $LOG_DIR/database.log' để xem log Database"
}

stop() {
    if [ ! -f "$PID_FILE" ]; then
        echo "Không tìm thấy file PID. Hệ thống có đang chạy không?"
        return 1
    fi

    PID=$(cat "$PID_FILE")
    if ps -p "$PID" > /dev/null 2>&1; then
        echo "Đang dừng hệ thống giám sát dữ liệu (PID: $PID)..."
        kill "$PID"
        sleep 3
        if ps -p "$PID" > /dev/null 2>&1; then
            echo "Tiến trình vẫn đang chạy, force kill..."
            kill -9 "$PID"
        fi
        rm "$PID_FILE"
        echo "Đã dừng hệ thống giám sát dữ liệu"
    else
        echo "Tiến trình không chạy, xóa file PID cũ"
        rm "$PID_FILE"
    fi
}

restart() {
    echo "Đang khởi động lại hệ thống..."
    stop
    sleep 3
    start
}

status() {
    if [ -f "$PID_FILE" ]; then
        PID=$(cat "$PID_FILE")
        if ps -p "$PID" > /dev/null 2>&1; then
            echo "Hệ thống giám sát dữ liệu đang chạy (PID: $PID)"
            echo "Thư mục log: $LOG_DIR/"
            echo ""
            echo "5 dòng log API gần nhất:"
            echo "----------------------------------------"
            tail -n 5 "$LOG_DIR/api.log" 2>/dev/null || echo "Chưa có log"
            echo "----------------------------------------"
            echo ""
            echo "5 dòng log Database gần nhất:"
            echo "----------------------------------------"
            tail -n 5 "$LOG_DIR/database.log" 2>/dev/null || echo "Chưa có log"
            echo "----------------------------------------"
        else
            echo "File PID tồn tại nhưng tiến trình không chạy"
        fi
    else
        echo "Hệ thống giám sát dữ liệu không chạy"
    fi
}

logs() {
    echo "Chọn loại log muốn xem:"
    echo "1) API log (api.log)"
    echo "2) Database log (database.log)"
    echo "3) Main log (main.log)"
    echo "4) Tất cả log (tail -f)"
    read -p "Nhập lựa chọn [1-4]: " choice
    
    case $choice in
        1)
            if [ -f "$LOG_DIR/api.log" ]; then
                echo "Hiển thị log API (nhấn Ctrl+C để thoát)..."
                tail -f "$LOG_DIR/api.log"
            else
                echo "Không tìm thấy file log: $LOG_DIR/api.log"
            fi
            ;;
        2)
            if [ -f "$LOG_DIR/database.log" ]; then
                echo "Hiển thị log Database (nhấn Ctrl+C để thoát)..."
                tail -f "$LOG_DIR/database.log"
            else
                echo "Không tìm thấy file log: $LOG_DIR/database.log"
            fi
            ;;
        3)
            if [ -f "$LOG_DIR/main.log" ]; then
                echo "Hiển thị log Main (nhấn Ctrl+C để thoát)..."
                tail -f "$LOG_DIR/main.log"
            else
                echo "Không tìm thấy file log: $LOG_DIR/main.log"
            fi
            ;;
        4)
            echo "Hiển thị tất cả log (nhấn Ctrl+C để thoát)..."
            tail -f "$LOG_DIR"/*.log 2>/dev/null
            ;;
        *)
            echo "Lựa chọn không hợp lệ"
            ;;
    esac
}

health() {
    echo "Đang kiểm tra tình trạng hệ thống..."
    echo ""
    
    # Kiểm tra file main.py
    if [ -f "$SCRIPT_DIR/src/main.py" ]; then
        echo "✓ Tìm thấy main script"
    else
        echo "✗ Không tìm thấy main script tại $SCRIPT_DIR/src/main.py"
    fi
    
    # Kiểm tra config files
    if [ -f "$SCRIPT_DIR/configs/common_config.json" ]; then
        echo "✓ Tìm thấy file config chung"
    else
        echo "✗ Không tìm thấy common_config.json"
    fi
    
    if [ -f "$SCRIPT_DIR/configs/check_api_config.json" ]; then
        echo "✓ Tìm thấy config API"
    else
        echo "✗ Không tìm thấy check_api_config.json"
    fi
    
    if [ -f "$SCRIPT_DIR/configs/check_database_config.json" ]; then
        echo "✓ Tìm thấy config Database"
    else
        echo "✗ Không tìm thấy check_database_config.json"
    fi
    
    if [ -f "$SCRIPT_DIR/configs/check_disk_config.json" ]; then
        echo "✓ Tìm thấy config Disk"
    else
        echo "✗ Không tìm thấy check_disk_config.json"
    fi
    
    # Kiểm tra Python virtual environment
    if [ -f "$SCRIPT_DIR/.venv/bin/python" ]; then
        echo "✓ Tìm thấy Python virtual environment"
        PYTHON_VERSION=$("$SCRIPT_DIR/.venv/bin/python" --version 2>&1)
        echo "  Phiên bản: $PYTHON_VERSION"
    else
        echo "✗ Không tìm thấy Python virtual environment tại $SCRIPT_DIR/.venv"
    fi
    
    # Kiểm tra các package Python cần thiết
    if [ -f "$SCRIPT_DIR/.venv/bin/python" ]; then
        echo ""
        echo "Kiểm tra các package cần thiết..."
        "$SCRIPT_DIR/.venv/bin/python" -c "import aiohttp; print('✓ aiohttp đã cài đặt')" 2>/dev/null || echo "✗ aiohttp chưa cài đặt"
        "$SCRIPT_DIR/.venv/bin/python" -c "import pymongo; print('✓ pymongo đã cài đặt')" 2>/dev/null || echo "✗ pymongo chưa cài đặt"
        "$SCRIPT_DIR/.venv/bin/python" -c "import psycopg2; print('✓ psycopg2 đã cài đặt')" 2>/dev/null || echo "✗ psycopg2 chưa cài đặt"
        "$SCRIPT_DIR/.venv/bin/python" -c "import pytz; print('✓ pytz đã cài đặt')" 2>/dev/null || echo "✗ pytz chưa cài đặt"
        "$SCRIPT_DIR/.venv/bin/python" -c "import requests; print('✓ requests đã cài đặt')" 2>/dev/null || echo "✗ requests chưa cài đặt"
    fi
    
    # Kiểm tra thư mục logs
    echo ""
    if [ -d "$LOG_DIR" ]; then
        echo "✓ Thư mục logs tồn tại"
        LOG_SIZE=$(du -sh "$LOG_DIR" 2>/dev/null | cut -f1)
        echo "  Dung lượng logs: $LOG_SIZE"
    else
        echo "✗ Thư mục logs không tồn tại"
    fi
    
    # Kiểm tra quyền thực thi
    if [ -x "$SCRIPT_DIR/.venv/bin/python" ]; then
        echo "✓ Python có quyền thực thi"
    else
        echo "⚠ Python có thể không có quyền thực thi"
    fi
}

case "$1" in
    start)
        start
        ;;
    stop)
        stop
        ;;
    restart)
        restart
        ;;
    status)
        status
        ;;
    logs)
        logs
        ;;
    health)
        health
        ;;
    *)
        echo "Cách sử dụng: $0 {start|stop|restart|status|logs|health}"
        echo ""
        echo "Các lệnh:"
        echo "  start   - Khởi động hệ thống giám sát dữ liệu"
        echo "  stop    - Dừng hệ thống giám sát dữ liệu"
        echo "  restart - Khởi động lại hệ thống"
        echo "  status  - Hiển thị trạng thái hiện tại"
        echo "  logs    - Xem log gần đây"
        echo "  health  - Kiểm tra tình trạng hệ thống"
        echo ""
        echo "Ví dụ:"
        echo "  ./run.sh start    # Khởi động hệ thống"
        echo "  ./run.sh status   # Xem trạng thái"
        echo "  ./run.sh logs     # Xem log"
        exit 1
        ;;
esac
