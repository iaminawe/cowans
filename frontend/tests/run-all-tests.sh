#!/bin/bash

# Icon Generation Test Runner
# This script runs all icon generation tests and generates a summary report

echo "🚀 Icon Generation Test Suite Runner"
echo "===================================="
echo ""

# Check if Python is available
if ! command -v python3 &> /dev/null; then
    echo "❌ Python 3 is required but not installed."
    exit 1
fi

# Create results directory
RESULTS_DIR="test-results-$(date +%Y%m%d-%H%M%S)"
mkdir -p "$RESULTS_DIR"

echo "📁 Results will be saved to: $RESULTS_DIR"
echo ""

# Function to run a test and capture results
run_test() {
    local test_name=$1
    local test_file=$2
    local output_file="$RESULTS_DIR/${test_name}.log"
    
    echo "🧪 Running $test_name..."
    echo "----------------------------------------"
    
    # Run the test and capture output
    python3 "$test_file" 2>&1 | tee "$output_file"
    
    # Check exit status
    if [ ${PIPESTATUS[0]} -eq 0 ]; then
        echo "✅ $test_name completed successfully"
    else
        echo "❌ $test_name failed with errors"
    fi
    
    echo ""
}

# Check API health first
echo "🏥 Checking API Health..."
API_HEALTH=$(curl -s -o /dev/null -w "%{http_code}" http://localhost:5001/api/health)

if [ "$API_HEALTH" != "200" ]; then
    echo "❌ API is not responding (HTTP $API_HEALTH)"
    echo "Please ensure the backend is running:"
    echo "  cd web_dashboard/backend && python app.py"
    exit 1
fi

echo "✅ API is healthy"
echo ""

# Run tests in sequence
echo "📋 Starting Test Sequence"
echo "========================"
echo ""

# 1. Quick smoke test
run_test "quick-test" "quick-icon-test.py"

# 2. UI responsiveness test
run_test "ui-responsiveness" "ui-responsiveness-test.py"

# 3. Comprehensive test suite (if quick tests pass)
if [ -f "$RESULTS_DIR/quick-test.log" ] && grep -q "All tests passed!" "$RESULTS_DIR/quick-test.log"; then
    echo "💪 Quick tests passed, running comprehensive suite..."
    run_test "comprehensive-suite" "icon-generation-test-suite.py"
else
    echo "⚠️  Skipping comprehensive suite due to quick test failures"
fi

# Generate summary report
echo ""
echo "📊 Generating Summary Report"
echo "============================"

SUMMARY_FILE="$RESULTS_DIR/SUMMARY.md"

cat > "$SUMMARY_FILE" << EOF
# Icon Generation Test Summary

**Date:** $(date)
**Results Directory:** $RESULTS_DIR

## Test Results

### Quick Test
$(grep -E "(✅|❌|Test Summary)" "$RESULTS_DIR/quick-test.log" | tail -10 || echo "No results found")

### UI Responsiveness
$(grep -E "(✅|❌|Overall Result:)" "$RESULTS_DIR/ui-responsiveness.log" | tail -5 || echo "No results found")

### Comprehensive Suite
$(grep -E "(Summary:|Total Tests:|Passed:|Failed:)" "$RESULTS_DIR/comprehensive-suite.log" | tail -5 || echo "Not run")

## Performance Metrics

### API Response Times
$(grep -A3 "API Call Response Times:" "$RESULTS_DIR/ui-responsiveness.log" || echo "No metrics found")

### Generation Times
$(grep -A2 "Generation Request Times:" "$RESULTS_DIR/ui-responsiveness.log" || echo "No metrics found")

## Artifacts

- Quick Test Log: \`quick-test.log\`
- UI Test Log: \`ui-responsiveness.log\`
- Comprehensive Test Log: \`comprehensive-suite.log\`
- JSON Reports: \`*.json\`

## Next Steps

1. Review failed tests in the log files
2. Check JSON reports for detailed metrics
3. Address any performance issues identified
4. Clean up test data if needed

EOF

echo ""
echo "✅ Test execution complete!"
echo ""
echo "📄 Summary saved to: $SUMMARY_FILE"
echo ""
echo "📊 Additional reports:"
find . -name "*.json" -mmin -5 | while read f; do
    echo "   - $(basename "$f")"
    mv "$f" "$RESULTS_DIR/" 2>/dev/null
done

echo ""
echo "💡 To view the summary:"
echo "   cat $SUMMARY_FILE"
echo ""
echo "🧹 To clean up test data:"
echo "   - Remove test collections from Shopify admin"
echo "   - Clear icon cache: curl -X POST http://localhost:5001/api/icons/cache/clear"
echo ""