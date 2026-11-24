#!/usr/bin/env bash
# ==============================================================================
# EZExam Reconstruction — E2E Test Runner Script
# Usage:
#   ./run_e2e_tests.sh [--all | --tier <1|2|3|4>] [--verbose]
# ==============================================================================

set -eo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$SCRIPT_DIR"

# Locate pytest binary (prefer local .venv)
if [ -f "$SCRIPT_DIR/.venv/bin/pytest" ]; then
    PYTEST_BIN="$SCRIPT_DIR/.venv/bin/pytest"
elif command -v pytest >/dev/null 2>&1; then
    PYTEST_BIN="$(command -v pytest)"
elif python3 -m pytest --version >/dev/null 2>&1; then
    PYTEST_BIN="python3 -m pytest"
else
    echo "ERROR: pytest not found. Please install dependencies or activate the virtualenv." >&2
    exit 1
fi

TARGET_TIER=""
RUN_ALL=true
VERBOSE_FLAG="-v"

usage() {
    local code="${1:-0}"
    cat <<EOF
EZExam E2E Test Suite Runner

Usage:
  ./run_e2e_tests.sh [OPTIONS]

Options:
  --all                 Run complete test suite (Tiers 1-4, 104+ tests) [Default]
  --tier <1|2|3|4>, -t  Run specific test tier:
                          1: Feature Coverage (45 isolated tests)
                          2: Boundary & Corner Cases (45 boundary tests)
                          3: Cross-Feature Pairwise (9 interaction tests)
                          4: Real-World Scenarios (5 full lifecycle tests)
  --quiet, -q           Reduce output verbosity
  --help, -h            Show this help message

Environment Variables:
  BASE_URL              Target live deployment (e.g. http://localhost:8000)
                        If unset, runs against the in-process Contract API engine.
EOF
    exit "$code"
}

# Parse command line flags
while [[ $# -gt 0 ]]; do
    case "$1" in
        --all)
            RUN_ALL=true
            TARGET_TIER=""
            shift
            ;;
        --tier|-t)
            if [ -z "$2" ] || [[ "$2" == -* ]]; then
                echo "Error: --tier requires an argument" >&2
                exit 1
            fi
            RUN_ALL=false
            TARGET_TIER="$2"
            shift 2
            ;;
        --quiet|-q)
            VERBOSE_FLAG=""
            shift
            ;;
        --help|-h)
            usage 0
            ;;
        *)
            echo "Unknown option: $1" >&2
            usage 1
            ;;
    esac
done

echo "=============================================================================="
echo "                   EZEXAM E2E TEST RUNNER EXECUTION                           "
echo "=============================================================================="
echo "Working Directory : $SCRIPT_DIR"
echo "Pytest Binary     : $PYTEST_BIN"
if [ -n "$BASE_URL" ]; then
    echo "Execution Target  : Live Backend ($BASE_URL)"
else
    echo "Execution Target  : In-Process Observable API Contract Engine"
fi
echo "=============================================================================="

START_TIME=$(date +%s)

if [ "$RUN_ALL" = true ]; then
    echo ">>> Running ALL Test Tiers (Tiers 1-4: 104 tests total)..."
    $PYTEST_BIN $VERBOSE_FLAG tests/
elif [ "$TARGET_TIER" = "1" ]; then
    echo ">>> Running Tier 1: Feature Coverage (45 tests)..."
    $PYTEST_BIN $VERBOSE_FLAG tests/tier1_features/
elif [ "$TARGET_TIER" = "2" ]; then
    echo ">>> Running Tier 2: Boundary & Corner Cases (45 tests)..."
    $PYTEST_BIN $VERBOSE_FLAG tests/tier2_boundaries/
elif [ "$TARGET_TIER" = "3" ]; then
    echo ">>> Running Tier 3: Cross-Feature Pairwise Combinations (9 tests)..."
    $PYTEST_BIN $VERBOSE_FLAG tests/tier3_pairwise/
elif [ "$TARGET_TIER" = "4" ]; then
    echo ">>> Running Tier 4: Real-World End-to-End Scenarios (5 tests)..."
    $PYTEST_BIN $VERBOSE_FLAG tests/tier4_scenarios/
else
    echo "ERROR: Invalid tier '$TARGET_TIER'. Expected 1, 2, 3, or 4." >&2
    exit 1
fi

EXIT_CODE=$?
END_TIME=$(date +%s)
DURATION=$((END_TIME - START_TIME))

echo "=============================================================================="
if [ $EXIT_CODE -eq 0 ]; then
    echo ">>> ALL TESTS PASSED SUCCESSFULLY (Duration: ${DURATION}s) [Exit Code: 0]"
else
    echo ">>> TEST EXECUTION FAILED (Duration: ${DURATION}s) [Exit Code: $EXIT_CODE]"
fi
echo "=============================================================================="

exit $EXIT_CODE
