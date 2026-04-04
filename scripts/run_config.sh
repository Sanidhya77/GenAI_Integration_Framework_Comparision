#!/bin/bash
# =============================================================================
# Run 5 repetitions of one test configuration
# =============================================================================
#
# Usage:
#   ./scripts/run_config.sh <framework> <endpoint> <concurrency> <server_pid>
#
# Examples:
#   ./scripts/run_config.sh flask inference 1 12345
#   ./scripts/run_config.sh django stream 5 12345
#   ./scripts/run_config.sh fastapi pipeline 50 12345
#
# Arguments:
#   framework   = flask | django | fastapi | tornado
#   endpoint    = inference | stream | pipeline
#   concurrency = 1 | 5 | 10 | 25 | 50 | 100
#   server_pid  = PID of the framework server worker process
#
# =============================================================================

FRAMEWORK=$1
ENDPOINT=$2
CONCURRENCY=$3
SERVER_PID=$4
HOST="http://localhost:8000"
TEST_DURATION="60s"
REST_BETWEEN_RUNS=$(( CONCURRENCY * 3 + 30 ))
WARMUP_REQUESTS=3

# Map endpoint to locust test file
case $ENDPOINT in
    inference) LOCUST_FILE="locust_tests/test_inference.py" ;;
    stream)    LOCUST_FILE="locust_tests/test_stream.py" ;;
    pipeline)  LOCUST_FILE="locust_tests/test_pipeline.py" ;;
    *)         echo "ERROR: Invalid endpoint '$ENDPOINT'. Use: inference | stream | pipeline"; exit 1 ;;
esac

# Validate arguments
if [ -z "$FRAMEWORK" ] || [ -z "$ENDPOINT" ] || [ -z "$CONCURRENCY" ] || [ -z "$SERVER_PID" ]; then
    echo "Usage: ./scripts/run_config.sh <framework> <endpoint> <concurrency> <server_pid>"
    echo "Example: ./scripts/run_config.sh flask inference 1 12345"
    exit 1
fi

# Verify server is running
if ! kill -0 $SERVER_PID 2>/dev/null; then
    echo "ERROR: No process found with PID $SERVER_PID"
    exit 1
fi

# Verify health endpoint
HEALTH=$(curl -s $HOST/health)
if [ $? -ne 0 ]; then
    echo "ERROR: Cannot connect to $HOST/health"
    exit 1
fi
echo "Server health: $HEALTH"

# Create output directory
OUTPUT_DIR="data/${FRAMEWORK}/${ENDPOINT}"
mkdir -p $OUTPUT_DIR

echo ""
echo "============================================================"
echo "CONFIGURATION: ${FRAMEWORK} / ${ENDPOINT} / concurrency ${CONCURRENCY}"
echo "============================================================"
echo "Locust file:    $LOCUST_FILE"
echo "Test duration:  $TEST_DURATION"
echo "Output dir:     $OUTPUT_DIR"
echo "Server PID:     $SERVER_PID"
echo "Runs:           5"
echo "============================================================"
echo ""

# Send warmup requests (discard results)
echo "Sending ${WARMUP_REQUESTS} warmup requests..."
for i in $(seq 1 $WARMUP_REQUESTS); do
    curl -s -X POST $HOST/api/${ENDPOINT} \
        -H "Content-Type: application/json" \
        -d '{"prompt": "What is generative AI and how is it used in modern web applications?"}' \
        > /dev/null 2>&1
done

# For streaming warmup, use the correct endpoint path
if [ "$ENDPOINT" = "stream" ]; then
    for i in $(seq 1 $WARMUP_REQUESTS); do
        curl -s -X POST $HOST/api/inference/stream \
            -H "Content-Type: application/json" \
            -d '{"prompt": "What is generative AI and how is it used in modern web applications?"}' \
            > /dev/null 2>&1
    done
fi

echo "Warmup complete."
echo ""

# Run 5 repetitions
for RUN in 1 2 3 4 5; do
    CSV_PREFIX="${OUTPUT_DIR}/c${CONCURRENCY}_run${RUN}"

    echo "------------------------------------------------------------"
    echo "RUN ${RUN}/5 — ${FRAMEWORK} / ${ENDPOINT} / c${CONCURRENCY}"
    echo "Started at: $(date '+%Y-%m-%d %H:%M:%S')"
    echo "------------------------------------------------------------"

    # Start resource monitor in background
    python monitoring/resource_monitor.py \
        --pid $SERVER_PID \
        --output "${CSV_PREFIX}_resources.csv" &
    MONITOR_PID=$!

    # Small delay to let monitor start
    sleep 2

    # Run Locust
    locust -f $LOCUST_FILE --headless \
        -u $CONCURRENCY -r $CONCURRENCY \
        -t $TEST_DURATION \
        --host $HOST \
        --csv $CSV_PREFIX

    # Stop resource monitor
    kill $MONITOR_PID 2>/dev/null
    wait $MONITOR_PID 2>/dev/null

    echo ""
    echo "Run ${RUN} complete. Files:"
    ls -la ${CSV_PREFIX}* 2>/dev/null
    echo ""

    # Rest between runs (skip after last run)
    if [ $RUN -lt 5 ]; then
        echo "Resting ${REST_BETWEEN_RUNS}s before next run..."
        sleep $REST_BETWEEN_RUNS
    fi
done

echo ""
echo "============================================================"
echo "CONFIGURATION COMPLETE: ${FRAMEWORK} / ${ENDPOINT} / c${CONCURRENCY}"
echo "============================================================"
echo "All files in: ${OUTPUT_DIR}/"
ls -la ${OUTPUT_DIR}/c${CONCURRENCY}_* 2>/dev/null
echo ""
CONFIG_REST=$(( CONCURRENCY * 3 + 60 ))
echo "Rest ${CONFIG_REST} seconds before next configuration..."
sleep $CONFIG_REST
echo "Ready for next configuration."