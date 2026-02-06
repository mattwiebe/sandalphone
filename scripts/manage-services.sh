#!/bin/bash
# Levi Service Management Script

BACKEND_PLIST="$HOME/Library/LaunchAgents/com.levi.mac-backend.plist"
BOT_PLIST="$HOME/Library/LaunchAgents/com.levi.telegram-bot.plist"

case "$1" in
    start)
        echo "Starting Levi services..."
        launchctl bootstrap "gui/$(id -u)" "$BACKEND_PLIST" 2>/dev/null
        launchctl bootstrap "gui/$(id -u)" "$BOT_PLIST" 2>/dev/null
        sleep 2
        $0 status
        ;;

    stop)
        echo "Stopping Levi services..."
        launchctl bootout "gui/$(id -u)" "$BACKEND_PLIST" 2>/dev/null
        launchctl bootout "gui/$(id -u)" "$BOT_PLIST" 2>/dev/null
        echo "Services stopped."
        ;;

    restart)
        echo "Restarting Levi services..."
        launchctl kickstart -k "gui/$(id -u)/com.levi.mac-backend" 2>/dev/null
        launchctl kickstart -k "gui/$(id -u)/com.levi.telegram-bot" 2>/dev/null
        ;;

    status)
        echo "Levi Service Status:"
        echo "===================="

        if launchctl list | grep -q "com.levi.mac-backend"; then
            echo "✅ Mac Backend: LOADED"
            launchctl list | grep "com.levi.mac-backend" | awk '{print "   PID:", $1, "| LastExit:", $3}'
        else
            echo "❌ Mac Backend: NOT LOADED"
        fi

        if launchctl list | grep -q "com.levi.telegram-bot"; then
            echo "✅ Telegram Bot: LOADED"
            launchctl list | grep "com.levi.telegram-bot" | awk '{print "   PID:", $1, "| LastExit:", $3}'
        else
            echo "❌ Telegram Bot: NOT LOADED"
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
