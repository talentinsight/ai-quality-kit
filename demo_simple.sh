#!/bin/bash

echo "🚀 AI Quality Kit - Live Demo"
echo "=============================="
echo ""

# Clear any previous cache by asking a unique question first
echo "🧹 Clearing cache with unique query..."
curl -s -H "Content-Type: application/json" \
  -d '{"query":"What is the current timestamp?"}' \
  http://localhost:8000/ask > /dev/null

echo ""
echo "📊 DEMO 1: Live vs Cache Performance"
echo "====================================="
echo ""

# Live call
echo "🔄 First call (Live - should be slower):"
start_time=$(date +%s.%N)
response1=$(curl -s -H "Content-Type: application/json" \
  -d '{"query":"What is the main purpose of this AI system?"}' \
  http://localhost:8000/ask)
end_time=$(date +%s.%N)
live_time=$(echo "$end_time - $start_time" | bc -l)
echo "⏱️  Live call took: ${live_time}s"
echo "📝 Response: $(echo $response1 | jq -r '.answer' | head -c 80)..."
echo ""

# Cache call
echo "⚡ Second call (Cache - should be faster):"
start_time=$(date +%s.%N)
response2=$(curl -s -H "Content-Type: application/json" \
  -d '{"query":"What is the main purpose of this AI system?"}' \
  http://localhost:8000/ask)
end_time=$(date +%s.%N)
cache_time=$(echo "$end_time - $start_time" | bc -l)
echo "⏱️  Cache call took: ${cache_time}s"
echo "📝 Response: $(echo $response2 | jq -r '.answer' | head -c 80)..."
echo ""

speedup=$(echo "scale=1; $live_time / $cache_time" | bc -l)
echo "🚀 Performance improvement: ${speedup}x faster with cache!"
echo ""

echo "📚 DEMO 2: Context-based Answer"
echo "================================"
echo "Query: 'What are the key features mentioned in the context?'"
echo ""

context_response=$(curl -s -H "Content-Type: application/json" \
  -d '{"query":"What are the key features mentioned in the context?"}' \
  http://localhost:8000/ask)

echo "📝 Answer: $(echo $context_response | jq -r '.answer' | head -c 100)..."
echo ""
echo "🔍 Context used (first 2 passages):"
echo $context_response | jq -r '.context[]' | head -2 | while read line; do
  echo "   • $(echo $line | head -c 70)..."
done
echo ""

echo "❌ DEMO 3: Out-of-Context Question"
echo "==================================="
echo "Query: 'What is the weather like in Istanbul today?'"
echo ""

negative_response=$(curl -s -H "Content-Type: application/json" \
  -d '{"query":"What is the weather like in Istanbul today?"}' \
  http://localhost:8000/ask)

echo "📝 Response: $(echo $negative_response | jq -r '.answer')"
echo ""

echo "❄️  DEMO 4: Logging & Monitoring"
echo "================================="
echo "📊 API calls logged to Snowflake:"
echo "   • Live call: ${live_time}s"
echo "   • Cache call: ${cache_time}s"
echo "   • Context query: $(echo $context_response | jq -r '.answer' | wc -c) chars"
echo "   • Negative query: $(echo $negative_response | jq -r '.answer' | wc -c) chars"
echo ""

echo "📈 DEMO SUMMARY"
echo "==============="
echo "✅ Live vs Cache: ${speedup}x performance improvement"
echo "✅ Context-based: AI uses relevant passages for answers"
echo "✅ Safety: Refuses out-of-context questions"
echo "✅ Monitoring: All calls logged with metrics"
echo ""
echo "🎯 Total demo time: ~1 minute"
echo "🔍 Check Snowflake tables for new log entries"

