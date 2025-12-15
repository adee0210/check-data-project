#!/bin/bash

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PID_FILE="$SCRIPT_DIR/check_data.pid"
LOG_DIR="$SCRIPT_DIR/logs"
LOG_FILE="$LOG_DIR/main.log"

mkdir -p "$LOG_DIR"

PYTHON_CMD="$SCRIPT_DIR/.venv/bin/python $SCRIPT_DIR/src/main.py"

start() {
    # Kiểm tra và tạo virtual environment nếu chưa có
    if [ ! -d "$SCRIPT_DIR/.venv" ]; then
        echo "Tạo virtual environment..."
        python3 -m venv "$SCRIPT_DIR/.venv"
        echo "Kích hoạt virtual environment và cài đặt packages..."
        source "$SCRIPT_DIR/.venv/bin/activate"
        pip install -r "$SCRIPT_DIR/requirements.txt"
        echo "Virtual environment đã được tạo và cài đặt xong."
    else
        echo "Virtual environment đã tồn tại, bỏ qua."
    fi

    if [ -f "$PID_FILE" ]; then
        PID=$(cat "$PID_FILE" | tr -d '\0')
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
    nohup bash -c "source $SCRIPT_DIR/.venv/bin/activate && $SCRIPT_DIR/.venv/bin/python $SCRIPT_DIR/src/main.py" > /dev/null 2>&1 &
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

    PID=$(cat "$PID_FILE" | tr -d '\0')
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
        PID=$(cat "$PID_FILE" | tr -d '\0')
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
        echo "Tim thay main script"
    else
        echo "Khong tim thay main script tai $SCRIPT_DIR/src/main.py"
    fi
    
    # Kiểm tra config files
    if [ -f "$SCRIPT_DIR/configs/common_config.json" ]; then
        echo "Tim thay file config chung"
    else
        echo "Khong tim thay common_config.json"
    fi
    
    if [ -f "$SCRIPT_DIR/configs/check_api_config.json" ]; then
        echo "Tim thay config API"
    else
        echo "Khong tim thay check_api_config.json"
    fi
    
    if [ -f "$SCRIPT_DIR/configs/check_database_config.json" ]; then
        echo "Tim thay config Database"
    else
        echo "Khong tim thay check_database_config.json"
    fi
    
    if [ -f "$SCRIPT_DIR/configs/check_disk_config.json" ]; then
        echo "Tim thay config Disk"
    else
        echo "Khong tim thay check_disk_config.json"
    fi
    
    # Kiểm tra Python virtual environment
    if [ -f "$SCRIPT_DIR/.venv/bin/python" ]; then
        echo "Tim thay Python virtual environment"
        PYTHON_VERSION=$("$SCRIPT_DIR/.venv/bin/python" --version 2>&1)
        echo "  Phien ban: $PYTHON_VERSION"
    else
        echo "Khong tim thay Python virtual environment tai $SCRIPT_DIR/.venv"
    fi
    
    # Kiểm tra các package Python cần thiết
    if [ -f "$SCRIPT_DIR/.venv/bin/python" ]; then
        echo ""
        echo "Kiem tra cac package can thiet..."
        "$SCRIPT_DIR/.venv/bin/python" -c "import aiohttp; print('aiohttp da cai dat')" 2>/dev/null || echo "aiohttp chua cai dat"
        "$SCRIPT_DIR/.venv/bin/python" -c "import pymongo; print('pymongo da cai dat')" 2>/dev/null || echo "pymongo chua cai dat"
        "$SCRIPT_DIR/.venv/bin/python" -c "import psycopg2; print('psycopg2 da cai dat')" 2>/dev/null || echo "psycopg2 chua cai dat"
        "$SCRIPT_DIR/.venv/bin/python" -c "import pytz; print('pytz da cai dat')" 2>/dev/null || echo "pytz da cai dat"
        "$SCRIPT_DIR/.venv/bin/python" -c "import requests; print('requests da cai dat')" 2>/dev/null || echo "requests chua cai dat"
    fi
    
    # Kiểm tra thư mục logs
    echo ""
    if [ -d "$LOG_DIR" ]; then
        echo "Thu muc logs ton tai"
        LOG_SIZE=$(du -sh "$LOG_DIR" 2>/dev/null | cut -f1)
        echo "  Dung luong logs: $LOG_SIZE"
    else
        echo "Thu muc logs khong ton tai"
    fi
    
    # Kiểm tra quyền thực thi
    if [ -x "$SCRIPT_DIR/.venv/bin/python" ]; then
        echo "Python co quyen thuc thi"
    else
        echo "Python co the khong co quyen thuc thi"
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
