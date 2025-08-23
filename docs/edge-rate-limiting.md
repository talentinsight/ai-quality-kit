# Edge Rate Limiting Configuration

This document provides configuration examples for implementing rate limiting at the edge (reverse proxy/load balancer) to complement the application-level rate limiting in AI Quality Kit.

## Overview

While AI Quality Kit includes built-in rate limiting middleware, implementing rate limiting at the edge provides additional benefits:

- **Performance**: Blocks requests before they reach the application
- **DDoS Protection**: Protects against volumetric attacks
- **Bandwidth Savings**: Reduces unnecessary data transfer
- **Multiple Layers**: Defense in depth approach

## NGINX Configuration

### Basic Rate Limiting

```nginx
http {
    # Define rate limiting zones
    limit_req_zone $binary_remote_addr zone=per_ip:10m rate=2r/s;
    limit_req_zone $http_authorization zone=per_token:10m rate=1r/s;
    
    # Define connection limiting
    limit_conn_zone $binary_remote_addr zone=conn_per_ip:10m;
    
    server {
        listen 80;
        server_name api.ai-quality-kit.com;
        
        # Global connection limit
        limit_conn conn_per_ip 10;
        
        # Health endpoints - no rate limiting
        location ~ ^/(healthz|readyz)$ {
            proxy_pass http://backend;
            proxy_set_header Host $host;
            proxy_set_header X-Real-IP $remote_addr;
            proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        }
        
        # Sensitive endpoints - strict rate limiting
        location ~ ^/(ask|orchestrator/run_tests)$ {
            # IP-based limiting: 2 requests/second burst=5
            limit_req zone=per_ip burst=5 nodelay;
            
            # Token-based limiting: 1 request/second burst=3
            limit_req zone=per_token burst=3 nodelay;
            
            proxy_pass http://backend;
            proxy_set_header Host $host;
            proxy_set_header X-Real-IP $remote_addr;
            proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
            proxy_set_header Authorization $http_authorization;
        }
        
        # Test data endpoints - moderate rate limiting
        location ~ ^/testdata/ {
            # IP-based limiting: 1 request/second burst=3
            limit_req zone=per_ip burst=3 nodelay;
            
            proxy_pass http://backend;
            proxy_set_header Host $host;
            proxy_set_header X-Real-IP $remote_addr;
            proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
            proxy_set_header Authorization $http_authorization;
        }
        
        # Default location for other endpoints
        location / {
            # Generous limits for other endpoints
            limit_req zone=per_ip burst=10 nodelay;
            
            proxy_pass http://backend;
            proxy_set_header Host $host;
            proxy_set_header X-Real-IP $remote_addr;
            proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
            proxy_set_header Authorization $http_authorization;
        }
    }
    
    # Backend upstream
    upstream backend {
        server 127.0.0.1:8000;
        # Add more servers for load balancing
        # server 127.0.0.1:8001;
        # server 127.0.0.1:8002;
    }
}
```

### Advanced NGINX Configuration with Redis

```nginx
http {
    # Lua script for Redis-based rate limiting
    lua_package_path "/etc/nginx/lua/?.lua;;";
    lua_shared_dict rate_limit_cache 10m;
    
    # Rate limiting with Redis backend
    access_by_lua_block {
        local resty_redis = require "resty.redis"
        local red = resty_redis:new()
        
        red:set_timeouts(1000, 1000, 1000)
        
        local ok, err = red:connect("127.0.0.1", 6379)
        if not ok then
            ngx.log(ngx.ERR, "failed to connect to redis: ", err)
            return
        end
        
        local key = "nginx_rl:" .. ngx.var.binary_remote_addr .. ":" .. ngx.var.uri
        local current = red:incr(key)
        
        if current == 1 then
            red:expire(key, 60)  -- 1 minute window
        end
        
        if current > 120 then  -- 120 requests per minute
            ngx.status = 429
            ngx.header["Retry-After"] = "60"
            ngx.say('{"error": "rate_limited", "retry_after_ms": 60000}')
            ngx.exit(429)
        end
        
        red:set_keepalive(10000, 100)
    }
}
```

### Custom Error Pages

```nginx
# Custom 429 error page
error_page 429 /rate_limit_error;

location = /rate_limit_error {
    internal;
    add_header Content-Type application/json always;
    add_header Retry-After 60 always;
    add_header X-RateLimit-Limit 120 always;
    add_header X-RateLimit-Remaining 0 always;
    
    return 429 '{"error": "rate_limited", "message": "Too many requests from your IP", "retry_after_ms": 60000}';
}
```

## Envoy Configuration

### Basic Envoy Rate Limiting

```yaml
# envoy.yaml
static_resources:
  listeners:
  - name: listener_0
    address:
      socket_address:
        address: 0.0.0.0
        port_value: 8080
    filter_chains:
    - filters:
      - name: envoy.filters.network.http_connection_manager
        typed_config:
          "@type": type.googleapis.com/envoy.extensions.filters.network.http_connection_manager.v3.HttpConnectionManager
          stat_prefix: ingress_http
          http_filters:
          # Rate limiting filter
          - name: envoy.filters.http.local_ratelimit
            typed_config:
              "@type": type.googleapis.com/udpa.type.v1.TypedStruct
              type_url: type.googleapis.com/envoy.extensions.filters.http.local_ratelimit.v3.LocalRateLimit
              value:
                stat_prefix: local_rate_limiter
                token_bucket:
                  max_tokens: 20
                  tokens_per_fill: 20
                  fill_interval: 60s
                filter_enabled:
                  runtime_key: local_rate_limit_enabled
                  default_value:
                    numerator: 100
                    denominator: HUNDRED
                filter_enforced:
                  runtime_key: local_rate_limit_enforced
                  default_value:
                    numerator: 100
                    denominator: HUNDRED
                response_headers_to_add:
                - append: false
                  header:
                    key: x-local-rate-limit
                    value: 'true'
                
          # Router filter (must be last)
          - name: envoy.filters.http.router
            typed_config:
              "@type": type.googleapis.com/envoy.extensions.filters.http.router.v3.Router
              
          route_config:
            name: local_route
            virtual_hosts:
            - name: ai_quality_kit
              domains: ["*"]
              routes:
              # Health endpoints - no rate limiting
              - match:
                  path: "/healthz"
                route:
                  cluster: backend
                typed_per_filter_config:
                  envoy.filters.http.local_ratelimit:
                    "@type": type.googleapis.com/udpa.type.v1.TypedStruct
                    type_url: type.googleapis.com/envoy.extensions.filters.http.local_ratelimit.v3.LocalRateLimit
                    value:
                      filter_enabled:
                        default_value:
                          numerator: 0
                          denominator: HUNDRED
              
              - match:
                  path: "/readyz"
                route:
                  cluster: backend
                typed_per_filter_config:
                  envoy.filters.http.local_ratelimit:
                    "@type": type.googleapis.com/udpa.type.v1.TypedStruct
                    type_url: type.googleapis.com/envoy.extensions.filters.http.local_ratelimit.v3.LocalRateLimit
                    value:
                      filter_enabled:
                        default_value:
                          numerator: 0
                          denominator: HUNDRED
              
              # Sensitive endpoints - strict limits
              - match:
                  prefix: "/ask"
                route:
                  cluster: backend
                typed_per_filter_config:
                  envoy.filters.http.local_ratelimit:
                    "@type": type.googleapis.com/udpa.type.v1.TypedStruct
                    type_url: type.googleapis.com/envoy.extensions.filters.http.local_ratelimit.v3.LocalRateLimit
                    value:
                      token_bucket:
                        max_tokens: 10
                        tokens_per_fill: 10
                        fill_interval: 60s
              
              - match:
                  prefix: "/orchestrator"
                route:
                  cluster: backend
                typed_per_filter_config:
                  envoy.filters.http.local_ratelimit:
                    "@type": type.googleapis.com/udpa.type.v1.TypedStruct
                    type_url: type.googleapis.com/envoy.extensions.filters.http.local_ratelimit.v3.LocalRateLimit
                    value:
                      token_bucket:
                        max_tokens: 5
                        tokens_per_fill: 5
                        fill_interval: 60s
              
              # Default route
              - match:
                  prefix: "/"
                route:
                  cluster: backend

  clusters:
  - name: backend
    connect_timeout: 30s
    type: LOGICAL_DNS
    dns_lookup_family: V4_ONLY
    load_assignment:
      cluster_name: backend
      endpoints:
      - lb_endpoints:
        - endpoint:
            address:
              socket_address:
                address: 127.0.0.1
                port_value: 8000
```

### Envoy with Redis Rate Limiting

```yaml
# For distributed rate limiting with Redis
static_resources:
  listeners:
  - name: listener_0
    address:
      socket_address: { address: 0.0.0.0, port_value: 8080 }
    filter_chains:
    - filters:
      - name: envoy.filters.network.http_connection_manager
        typed_config:
          "@type": type.googleapis.com/envoy.extensions.filters.network.http_connection_manager.v3.HttpConnectionManager
          stat_prefix: ingress_http
          http_filters:
          # Global rate limiting filter
          - name: envoy.filters.http.ratelimit
            typed_config:
              "@type": type.googleapis.com/envoy.extensions.filters.http.ratelimit.v3.RateLimit
              domain: ai_quality_kit
              stage: 0
              rate_limit_service:
                grpc_service:
                  envoy_grpc:
                    cluster_name: rate_limit_service
                  timeout: 0.25s
                transport_api_version: V3
          
          # Router filter
          - name: envoy.filters.http.router
            typed_config:
              "@type": type.googleapis.com/envoy.extensions.filters.http.router.v3.Router
              
          route_config:
            name: local_route
            virtual_hosts:
            - name: ai_quality_kit
              domains: ["*"]
              rate_limits:
              - stage: 0
                actions:
                - request_headers:
                    header_name: ":path"
                    descriptor_key: "path"
                - request_headers:
                    header_name: "authorization"
                    descriptor_key: "token"
                - remote_address:
                    descriptor_key: "client_ip"
              routes:
              - match: { prefix: "/" }
                route: { cluster: backend }

  clusters:
  - name: backend
    connect_timeout: 30s
    type: LOGICAL_DNS
    dns_lookup_family: V4_ONLY
    load_assignment:
      cluster_name: backend
      endpoints:
      - lb_endpoints:
        - endpoint:
            address:
              socket_address:
                address: 127.0.0.1
                port_value: 8000

  - name: rate_limit_service
    type: STRICT_DNS
    connect_timeout: 30s
    load_assignment:
      cluster_name: rate_limit_service
      endpoints:
      - lb_endpoints:
        - endpoint:
            address:
              socket_address:
                address: ratelimit
                port_value: 8081
```

## HAProxy Configuration

```
# haproxy.cfg
global
    daemon
    
defaults
    mode http
    timeout connect 5000ms
    timeout client 50000ms
    timeout server 50000ms
    
frontend ai_quality_kit_frontend
    bind *:80
    
    # Rate limiting using stick tables
    stick-table type ip size 100k expire 1m store http_req_rate(1m)
    http-request track-sc0 src
    
    # Block if more than 120 requests per minute from same IP
    http-request deny if { sc_http_req_rate(0) gt 120 }
    
    # Route to appropriate backend based on path
    use_backend health_backend if { path_beg /healthz } or { path_beg /readyz }
    use_backend api_backend if { path_beg /ask } or { path_beg /orchestrator }
    use_backend testdata_backend if { path_beg /testdata }
    default_backend api_backend

backend health_backend
    # No additional rate limiting for health checks
    server web1 127.0.0.1:8000 check

backend api_backend
    # Strict rate limiting for API endpoints
    stick-table type string len 32 size 100k expire 1m store http_req_rate(1m)
    http-request track-sc1 req.hdr(Authorization)
    http-request deny if { sc_http_req_rate(1) gt 60 }
    
    server web1 127.0.0.1:8000 check

backend testdata_backend
    # Moderate rate limiting for testdata endpoints  
    stick-table type string len 32 size 100k expire 1m store http_req_rate(1m)
    http-request track-sc2 req.hdr(Authorization)
    http-request deny if { sc_http_req_rate(2) gt 30 }
    
    server web1 127.0.0.1:8000 check
```

## AWS Application Load Balancer

```json
{
  "Rules": [
    {
      "Priority": 100,
      "Conditions": [
        {
          "Field": "path-pattern",
          "Values": ["/healthz", "/readyz"]
        }
      ],
      "Actions": [
        {
          "Type": "forward",
          "TargetGroupArn": "arn:aws:elasticloadbalancing:us-east-1:123456789012:targetgroup/ai-quality-kit/1234567890abcdef"
        }
      ]
    },
    {
      "Priority": 200,
      "Conditions": [
        {
          "Field": "path-pattern", 
          "Values": ["/ask*", "/orchestrator*"]
        }
      ],
      "Actions": [
        {
          "Type": "forward",
          "TargetGroupArn": "arn:aws:elasticloadbalancing:us-east-1:123456789012:targetgroup/ai-quality-kit/1234567890abcdef"
        }
      ]
    }
  ]
}
```

For AWS ALB, additional rate limiting can be implemented using:
- **AWS WAF**: Web Application Firewall with rate-based rules
- **AWS Shield**: DDoS protection
- **CloudFront**: CDN with rate limiting capabilities

## Cloudflare Configuration

```javascript
// Cloudflare Workers script for rate limiting
addEventListener('fetch', event => {
  event.respondWith(handleRequest(event.request))
})

async function handleRequest(request) {
  const url = new URL(request.url)
  
  // Skip rate limiting for health endpoints
  if (url.pathname.startsWith('/healthz') || url.pathname.startsWith('/readyz')) {
    return fetch(request)
  }
  
  // Get client IP
  const clientIP = request.headers.get('CF-Connecting-IP')
  
  // Get authorization token
  const authHeader = request.headers.get('Authorization')
  const token = authHeader ? authHeader.replace('Bearer ', '') : null
  
  // Check rate limits
  const ipKey = `rate_limit:ip:${clientIP}`
  const tokenKey = token ? `rate_limit:token:${token}` : null
  
  // IP-based rate limiting
  const ipCount = await incrementCounter(ipKey, 60) // 1 minute window
  if (ipCount > 120) {
    return new Response(
      JSON.stringify({
        error: 'rate_limited',
        retry_after_ms: 60000
      }),
      {
        status: 429,
        headers: {
          'Content-Type': 'application/json',
          'Retry-After': '60'
        }
      }
    )
  }
  
  // Token-based rate limiting
  if (tokenKey) {
    const tokenCount = await incrementCounter(tokenKey, 60)
    if (tokenCount > 60) {
      return new Response(
        JSON.stringify({
          error: 'rate_limited',
          retry_after_ms: 60000
        }),
        {
          status: 429,
          headers: {
            'Content-Type': 'application/json',
            'Retry-After': '60'
          }
        }
      )
    }
  }
  
  // Forward request
  return fetch(request)
}

async function incrementCounter(key, windowSeconds) {
  // Implementation depends on your KV store or Durable Objects
  // This is a simplified example
  const current = await KV.get(key) || 0
  const newValue = parseInt(current) + 1
  await KV.put(key, newValue.toString(), { expirationTtl: windowSeconds })
  return newValue
}
```

## Best Practices

### Layered Rate Limiting

Implement multiple layers for comprehensive protection:

1. **Edge/CDN**: Coarse-grained protection against volumetric attacks
2. **Load Balancer**: Network-level rate limiting by IP/region
3. **Reverse Proxy**: Application-aware rate limiting by endpoint
4. **Application**: Fine-grained rate limiting by user/token

### Monitoring and Alerting

Monitor rate limiting effectiveness:

```bash
# NGINX log analysis
tail -f /var/log/nginx/access.log | grep "429"

# Check rate limit hit rates
curl -s http://localhost/nginx_status | grep "limit_req"

# Application metrics
curl -s http://localhost:8000/metrics | grep rate_limit
```

### Configuration Recommendations

- **Start Conservative**: Begin with generous limits and tighten based on usage patterns
- **Monitor Impact**: Track false positives and legitimate user impact  
- **Graceful Degradation**: Implement proper error responses and retry guidance
- **Whitelist Critical**: Exempt health checks and monitoring from rate limits
- **Geographic Considerations**: Adjust limits based on user distribution

This multi-layered approach ensures robust protection while maintaining good user experience.
