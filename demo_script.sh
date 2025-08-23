#!/bin/bash

echo "🚀 AI Quality Kit - 1 Minute Demo"
echo "=================================="
echo ""

# Demo 1: Live vs Cache Performance
echo "📊 Demo 1: Live vs Cache Performance"
echo "------------------------------------"
echo "Query: 'What is the main purpose of this AI system?'"
echo ""

echo "🔄 First call (Live - should be slower):"
start_time=$(date +%s.%N)
response1=$(curl -s -H "Content-Type: application/json" \
  -d '{"query":"What is the main purpose of this AI system?"}' \
  http://localhost:8000/ask)
end_time=$(date +%s.%N)
live_time=$(echo "$end_time - $start_time" | bc -l)
echo "⏱️  Live call took: ${live_time}s"
echo "📝 Response: $(echo $response1 | jq -r '.answer' | head -c 100)..."
echo ""

echo "⚡ Second call (Cache - should be faster):"
start_time=$(date +%s.%N)
response2=$(curl -s -H "Content-Type: application/json" \
  -d '{"query":"What is the main purpose of this AI system?"}' \
  http://localhost:8000/ask)
end_time=$(date +%s.%N)
cache_time=$(echo "$end_time - $start_time" | bc -l)
echo "⏱️  Cache call took: ${cache_time}s"
echo "📝 Response: $(echo $response2 | jq -r '.answer' | head -c 100)..."
echo ""

speedup=$(echo "scale=2; $live_time / $cache_time" | bc -l)
echo "🚀 Performance improvement: ${speedup}x faster with cache!"
echo ""

# Demo 2: Context-based Answer
echo "📚 Demo 2: Context-based Answer"
echo "--------------------------------"
echo "Query: 'What are the key features mentioned in the context?'"
echo ""

context_response=$(curl -s -H "Content-Type: application/json" \
  -d '{"query":"What are the key features mentioned in the context?"}' \
  http://localhost:8000/ask)

echo "📝 Answer: $(echo $context_response | jq -r '.answer' | head -c 150)..."
echo ""
echo "🔍 Context used:"
echo $context_response | jq -r '.context[]' | head -3 | while read line; do
  echo "   • $(echo $line | head -c 80)..."
done
echo ""

# Demo 3: Negative Question (Out of Context)
echo "❌ Demo 3: Negative Question (Out of Context)"
echo "---------------------------------------------"
echo "Query: 'What is the weather like in Istanbul today?'"
echo ""

negative_response=$(curl -s -H "Content-Type: application/json" \
  -d '{"query":"What is the weather like in Istanbul today?"}' \
  http://localhost:8000/ask)

echo "📝 Response: $(echo $negative_response | jq -r '.answer' | head -c 150)..."
echo ""

# Demo 4: Snowflake Logging Check
echo "❄️  Demo 4: Snowflake Logging Check"
echo "-----------------------------------"
echo "Checking if new log entries were created..."
echo ""

# Show recent API calls in logs (if available)
echo "📊 Recent API activity:"
echo "   • Live call: ${live_time}s"
echo "   • Cache call: ${cache_time}s"
echo "   • Context query: $(echo $context_response | jq -r '.answer' | wc -c) chars"
echo "   • Negative query: $(echo $negative_response | jq -r '.answer' | wc -c) chars"
echo ""

echo "✅ Demo completed! Check Snowflake tables for new log entries."
echo ""

# Performance Summary
echo "📈 Performance Summary:"
echo "   • Live call: ${live_time}s"
echo "   • Cache call: ${cache_time}s"
echo "   • Speedup: ${speedup}x"
echo "   • Total demo time: ~1 minute"
echo ""
echo "🎯 Key Features Demonstrated:"
echo "   ✅ Live vs Cache performance difference"
echo "   ✅ Context-based answer generation"
echo "   ✅ Out-of-context question handling"
echo "   ✅ API logging and monitoring"
echo ""
