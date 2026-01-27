##### Note! The filepaths only work if run from in this directory. So logging only occurs in dev.


SCRIPT_DIR="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" &> /dev/null && pwd)"
LOG_DIR=$SCRIPT_DIR/logs

#!/bin/bash
VENV_PATH=~/venvs/agentic

FREEPORT_LOG=$LOG_DIR/freeport.log
SERVER_LOG_2=$LOG_DIR/llm_server-py.log
PID_FILE=$LOG_DIR/llm_server.pid

source "$VENV_PATH/bin/activate"

echo "VIRTUAL_ENV is set to: $VIRTUAL_ENV"

#cd ~/Software/Code/gedit-textflow/textflow

bash free_port_19953.sh > "$FREEPORT_LOG" 2>&1

PORT=19953
RETRIES=5
SLEEP=1
for i in $(seq 1 $RETRIES); do
  PID=$(lsof -t -i :"$PORT")
  if [ -z "$PID" ]; then


    echo "Port $PORT is now free (attempt $i/$RETRIES)."
    # Start the server only if the port is free
    nohup python3 $SCRIPT_DIR/llm_server.py > "$SERVER_LOG_2" 2>&1 &
    echo $! > "$PID_FILE"
    echo "LLM server started with PID $(cat $PID_FILE)"


    break
  else
    echo "Port $PORT still in use by PID(s): $PID (attempt $i/$RETRIES). Waiting..."
    sleep "$SLEEP"
  fi
  if [ "$i" -eq "$RETRIES" ]; then
    echo "Failed to free port $PORT after $RETRIES attempts. Exiting."
    exit 1
  fi
done