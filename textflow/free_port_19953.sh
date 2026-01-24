#bash

PORT=19953

PID=$(lsof -t -i :"$PORT" | head -n 1)

echo "Checking port $PORT..."
echo "Found PID: $PID"

if [ -n "$PID" ]; then
  echo "Port $PORT is in use by PID: $PID. Killing..."
  kill "$PID"
  sleep 1
  if kill -0 "$PID" 2>/dev/null; then
    echo "PID $PID did not exit. Force killing..."
    kill -9 "$PID"
  fi
else
  echo "Port $PORT is free."
fi