#!/usr/bin/env python3
"""
Test Results Visualizer

Creates visual charts from test result JSON files.
"""

import json
import os
import glob
from datetime import datetime
import matplotlib.pyplot as plt
import matplotlib.dates as mdates
from typing import Dict, List, Any

def load_test_results(directory: str = ".") -> List[Dict[str, Any]]:
    """Load all test result JSON files from directory."""
    results = []
    
    # Find all JSON result files
    patterns = [
        "icon_test_report_*.json",
        "ui_responsiveness_report_*.json"
    ]
    
    for pattern in patterns:
        for file_path in glob.glob(os.path.join(directory, pattern)):
            try:
                with open(file_path, 'r') as f:
                    data = json.load(f)
                    data['file_name'] = os.path.basename(file_path)
                    results.append(data)
            except Exception as e:
                print(f"Error loading {file_path}: {e}")
    
    return sorted(results, key=lambda x: x.get('timestamp', ''))

def plot_test_summary(results: List[Dict[str, Any]]):
    """Create test summary visualization."""
    if not results:
        print("No test results found")
        return
    
    fig, ((ax1, ax2), (ax3, ax4)) = plt.subplots(2, 2, figsize=(15, 10))
    fig.suptitle('Icon Generation Test Results Dashboard', fontsize=16)
    
    # 1. Pass/Fail Rate Over Time
    timestamps = []
    pass_rates = []
    
    for result in results:
        if 'summary' in result:
            timestamp = datetime.fromisoformat(result['timestamp'])
            timestamps.append(timestamp)
            
            total = result['summary']['total_tests']
            passed = result['summary']['passed']
            pass_rate = (passed / total * 100) if total > 0 else 0
            pass_rates.append(pass_rate)
    
    if timestamps:
        ax1.plot(timestamps, pass_rates, 'go-', linewidth=2, markersize=8)
        ax1.set_title('Test Pass Rate Over Time')
        ax1.set_xlabel('Date')
        ax1.set_ylabel('Pass Rate (%)')
        ax1.grid(True, alpha=0.3)
        ax1.set_ylim(0, 105)
        
        # Format x-axis dates
        ax1.xaxis.set_major_formatter(mdates.DateFormatter('%m/%d %H:%M'))
        plt.setp(ax1.xaxis.get_majorticklabels(), rotation=45)
    
    # 2. Response Time Distribution
    response_times = []
    
    for result in results:
        if 'response_times' in result:
            api_times = result['response_times'].get('api_calls', {})
            if 'mean' in api_times:
                response_times.extend([api_times['mean']] * api_times.get('count', 1))
    
    if response_times:
        ax2.hist(response_times, bins=20, color='skyblue', edgecolor='black', alpha=0.7)
        ax2.set_title('API Response Time Distribution')
        ax2.set_xlabel('Response Time (seconds)')
        ax2.set_ylabel('Frequency')
        ax2.grid(True, alpha=0.3)
        
        # Add statistics
        mean_time = sum(response_times) / len(response_times)
        ax2.axvline(mean_time, color='red', linestyle='--', linewidth=2, label=f'Mean: {mean_time:.3f}s')
        ax2.legend()
    
    # 3. Generation Success Rate
    total_generated = 0
    total_failed = 0
    
    for result in results:
        if 'summary' in result:
            total_generated += result['summary'].get('generated_icons', 0)
        
        if 'test_results' in result:
            for test in result['test_results']:
                if test.get('test_name', '').startswith('Generate icon'):
                    if test.get('passed'):
                        total_generated += 1
                    else:
                        total_failed += 1
    
    if total_generated + total_failed > 0:
        sizes = [total_generated, total_failed]
        labels = ['Successful', 'Failed']
        colors = ['#4CAF50', '#F44336']
        
        ax3.pie(sizes, labels=labels, colors=colors, autopct='%1.1f%%', startangle=90)
        ax3.set_title('Icon Generation Success Rate')
    
    # 4. Performance Metrics
    metrics_data = {
        'Avg Response': [],
        'Max Response': [],
        'P95 Response': []
    }
    
    for result in results:
        if 'test_results' in result and 'concurrent_api' in result['test_results']:
            api_result = result['test_results']['concurrent_api']
            metrics_data['Avg Response'].append(api_result.get('avg_response', 0))
            metrics_data['Max Response'].append(api_result.get('max_response', 0))
            metrics_data['P95 Response'].append(api_result.get('p95_response', 0))
    
    if any(metrics_data.values()):
        x_pos = range(len(metrics_data))
        
        for i, (metric, values) in enumerate(metrics_data.items()):
            if values:
                avg_value = sum(values) / len(values)
                ax4.bar(i, avg_value, label=metric, alpha=0.7)
        
        ax4.set_title('Average Performance Metrics')
        ax4.set_ylabel('Time (seconds)')
        ax4.set_xticks(x_pos)
        ax4.set_xticklabels(metrics_data.keys(), rotation=45)
        ax4.grid(True, alpha=0.3, axis='y')
    
    plt.tight_layout()
    
    # Save the plot
    timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
    filename = f'test_results_dashboard_{timestamp}.png'
    plt.savefig(filename, dpi=150, bbox_inches='tight')
    print(f"Dashboard saved to: {filename}")
    
    plt.show()

def generate_html_report(results: List[Dict[str, Any]]):
    """Generate an HTML report with test results."""
    html_content = """
<!DOCTYPE html>
<html>
<head>
    <title>Icon Generation Test Report</title>
    <style>
        body {
            font-family: Arial, sans-serif;
            margin: 20px;
            background-color: #f5f5f5;
        }
        .container {
            max-width: 1200px;
            margin: 0 auto;
            background-color: white;
            padding: 20px;
            border-radius: 8px;
            box-shadow: 0 2px 4px rgba(0,0,0,0.1);
        }
        h1 {
            color: #333;
            border-bottom: 2px solid #007bff;
            padding-bottom: 10px;
        }
        .summary {
            display: grid;
            grid-template-columns: repeat(auto-fit, minmax(200px, 1fr));
            gap: 20px;
            margin: 20px 0;
        }
        .metric-card {
            background-color: #f8f9fa;
            padding: 20px;
            border-radius: 8px;
            text-align: center;
            border: 1px solid #e9ecef;
        }
        .metric-value {
            font-size: 2em;
            font-weight: bold;
            color: #007bff;
        }
        .metric-label {
            color: #6c757d;
            margin-top: 5px;
        }
        .test-result {
            margin: 10px 0;
            padding: 15px;
            border-radius: 5px;
        }
        .passed {
            background-color: #d4edda;
            border: 1px solid #c3e6cb;
        }
        .failed {
            background-color: #f8d7da;
            border: 1px solid #f5c6cb;
        }
        .timestamp {
            color: #6c757d;
            font-size: 0.9em;
        }
        table {
            width: 100%;
            border-collapse: collapse;
            margin: 20px 0;
        }
        th, td {
            padding: 10px;
            text-align: left;
            border-bottom: 1px solid #dee2e6;
        }
        th {
            background-color: #007bff;
            color: white;
        }
        tr:hover {
            background-color: #f8f9fa;
        }
    </style>
</head>
<body>
    <div class="container">
        <h1>Icon Generation Test Report</h1>
        <p class="timestamp">Generated: {timestamp}</p>
        
        <div class="summary">
            <div class="metric-card">
                <div class="metric-value">{total_tests}</div>
                <div class="metric-label">Total Tests</div>
            </div>
            <div class="metric-card">
                <div class="metric-value">{pass_rate}%</div>
                <div class="metric-label">Pass Rate</div>
            </div>
            <div class="metric-card">
                <div class="metric-value">{avg_response_time}s</div>
                <div class="metric-label">Avg Response Time</div>
            </div>
            <div class="metric-card">
                <div class="metric-value">{total_icons}</div>
                <div class="metric-label">Icons Generated</div>
            </div>
        </div>
        
        <h2>Test Results</h2>
        <table>
            <tr>
                <th>Test Name</th>
                <th>Status</th>
                <th>Duration</th>
                <th>Details</th>
            </tr>
            {test_rows}
        </table>
        
        <h2>Performance Metrics</h2>
        {performance_section}
    </div>
</body>
</html>
    """
    
    # Calculate summary metrics
    total_tests = 0
    passed_tests = 0
    total_response_times = []
    total_icons = 0
    test_rows = []
    
    for result in results:
        if 'summary' in result:
            total_tests += result['summary'].get('total_tests', 0)
            passed_tests += result['summary'].get('passed', 0)
            total_icons += result['summary'].get('generated_icons', 0)
        
        if 'test_results' in result:
            for test in result['test_results']:
                status = "✅ Passed" if test.get('passed') else "❌ Failed"
                duration = f"{test.get('duration', 0):.2f}s"
                details = test.get('error', '') or str(test.get('details', ''))[:100]
                
                test_rows.append(f"""
                    <tr class="{'passed' if test.get('passed') else 'failed'}">
                        <td>{test.get('test_name', 'Unknown')}</td>
                        <td>{status}</td>
                        <td>{duration}</td>
                        <td>{details}</td>
                    </tr>
                """)
        
        if 'response_times' in result:
            api_times = result['response_times'].get('api_calls', {})
            if 'mean' in api_times:
                total_response_times.append(api_times['mean'])
    
    # Calculate final metrics
    pass_rate = int((passed_tests / total_tests * 100) if total_tests > 0 else 0)
    avg_response_time = f"{sum(total_response_times) / len(total_response_times):.3f}" if total_response_times else "N/A"
    
    # Performance section
    performance_html = """
        <div class="summary">
            <div class="metric-card">
                <div class="metric-value">Coming Soon</div>
                <div class="metric-label">P95 Response Time</div>
            </div>
            <div class="metric-card">
                <div class="metric-value">Coming Soon</div>
                <div class="metric-label">WebSocket Latency</div>
            </div>
            <div class="metric-card">
                <div class="metric-value">Coming Soon</div>
                <div class="metric-label">Batch Success Rate</div>
            </div>
        </div>
    """
    
    # Generate final HTML
    html = html_content.format(
        timestamp=datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
        total_tests=total_tests,
        pass_rate=pass_rate,
        avg_response_time=avg_response_time,
        total_icons=total_icons,
        test_rows='\n'.join(test_rows),
        performance_section=performance_html
    )
    
    # Save HTML report
    filename = f'test_report_{datetime.now().strftime("%Y%m%d_%H%M%S")}.html'
    with open(filename, 'w') as f:
        f.write(html)
    
    print(f"HTML report saved to: {filename}")

def main():
    """Main function to generate visualizations."""
    print("📊 Icon Generation Test Results Visualizer")
    print("=" * 50)
    
    # Load test results
    results = load_test_results()
    
    if not results:
        print("❌ No test result files found in current directory")
        print("Make sure to run the tests first to generate JSON reports")
        return
    
    print(f"✅ Found {len(results)} test result files")
    
    # Generate visualizations
    try:
        import matplotlib
        plot_test_summary(results)
    except ImportError:
        print("⚠️  matplotlib not installed, skipping charts")
        print("Install with: pip install matplotlib")
    
    # Generate HTML report
    generate_html_report(results)
    
    print("\n✅ Visualization complete!")

if __name__ == "__main__":
    main()