#!/bin/bash
# Levi Service Management Script

BACKEND_PLIST="$HOME/Library/LaunchAgents/com.levi.mac-backend.plist"
BOT_PLIST="$HOME/Library/LaunchAgents/com.levi.telegram-bot.plist"

case "$1" in
    start)
        echo "Starting Levi services..."
        launchctl load "$BACKEND_PLIST" 2>/dev/null
        launchctl load "$BOT_PLIST" 2>/dev/null
        sleep 2
        $0 status
        ;;

    stop)
        echo "Stopping Levi services..."
        launchctl unload "$BACKEND_PLIST" 2>/dev/null
        launchctl unload "$BOT_PLIST" 2>/dev/null
        echo "Services stopped."
        ;;

    restart)
        echo "Restarting Levi services..."
        $0 stop
        sleep 1
        $0 start
        ;;

    status)
        echo "Levi Service Status:"
        echo "===================="

        if ps aux | grep -v grep | grep "python.*main.py" > /dev/null; then
            echo "✅ Mac Backend: RUNNING"
            ps aux | grep -v grep | grep "python.*main.py" | awk '{print "   PID:", $2, "| Memory:", $6/1024 "MB"}'
        else
            echo "❌ Mac Backend: NOT RUNNING"
        fi

        if ps aux | grep -v grep | grep "python.*telegram_bot.py" > /dev/null; then
            echo "✅ Telegram Bot: RUNNING"
            ps aux | grep -v grep | grep "python.*telegram_bot.py" | awk '{print "   PID:", $2, "| Memory:", $6/1024 "MB"}'
        else
            echo "❌ Telegram Bot: NOT RUNNING"
        fi
        ;;

    logs)
        echo "Showing recent logs..."
        echo ""
        echo "=== Mac Backend Logs ==="
        tail -20 ~/levi/logs/mac-backend.log 2>/dev/null || echo "No logs yet"
        echo ""
        echo "=== Telegram Bot Logs ==="
        tail -20 ~/levi/logs/telegram-bot.log 2>/dev/null || echo "No logs yet"
        ;;

    follow)
        echo "Following logs (Ctrl+C to stop)..."
        tail -f ~/levi/logs/*.log
        ;;

    *)
        echo "Levi Service Manager"
        echo "===================="
        echo "Usage: $0 {start|stop|restart|status|logs|follow}"
        echo ""
        echo "Commands:"
        echo "  start   - Start both services"
        echo "  stop    - Stop both services"
        echo "  restart - Restart both services"
        echo "  status  - Check if services are running"
        echo "  logs    - Show recent logs"
        echo "  follow  - Follow logs in real-time"
        exit 1
        ;;
esac
