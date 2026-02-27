# StrictDoc Service Monitoring

Comprehensive monitoring setup with Prometheus and Grafana for StrictDoc Service.

## Quick Start

### 1. Start Monitoring Stack

```bash
./start-monitoring.sh
```

This will:
- Build the StrictDoc service Docker image
- Start Prometheus, Grafana, and StrictDoc service
- Wait for all services to be healthy
- Generate initial test traffic
- Display access URLs

### 2. Generate Test Load

```bash
# Generate 100 requests with 10 concurrent workers
./generate-load.sh

# Custom load: 500 requests with 20 concurrent workers
./generate-load.sh 500 20
```

### 3. View Metrics

#### Grafana Dashboard
- URL: http://localhost:3000/d/strictdoc-service
- Username: `admin`
- Password: `admin`
- Pre-configured with all metrics

#### Prometheus
- URL: http://localhost:9090
- Query metrics directly
- View targets: http://localhost:9090/targets

### 4. Stop Monitoring Stack

```bash
./stop-monitoring.sh
```

## Architecture

```
┌─────────────────┐
│  StrictDoc      │
│  Service        │──────┐
│  :9083          │      │
│  Metrics :9183  │      │
└─────────────────┘      │
                         │ Scrapes /metrics
                         ▼
                  ┌─────────────┐
                  │ Prometheus  │
                  │ :9090       │
                  └─────────────┘
                         │
                         │ Data source
                         ▼
                  ┌─────────────┐
                  │  Grafana    │
                  │  :3000      │
                  └─────────────┘
```

## Available Metrics

### Export Metrics
- `strictdoc_exports_total` - Total successful exports (labeled by format)
- `strictdoc_export_failures_total` - Total failed exports (labeled by format)
- `strictdoc_export_error_rate_percent` - Export error rate as percentage

### Performance Metrics
- `strictdoc_export_duration_seconds` - Export time histogram (labeled by format)
- `avg_strictdoc_export_time_seconds` - Average export time

### Size Metrics
- `strictdoc_request_body_bytes` - Input document size histogram
- `strictdoc_response_body_bytes` - Output document size histogram

### Service Metrics
- `uptime_seconds` - Service uptime
- `active_exports` - Current active export count
- `strictdoc_info` - Service and StrictDoc version information

## Grafana Dashboard Panels

1. **Status** - Service up/down status
2. **Uptime** - Total service uptime
3. **Active Exports** - Current concurrent operations
4. **Error Rate** - Export error percentage
5. **Total Exports** - Cumulative successful exports
6. **Avg Export Time** - Average export duration
7. **Total Failures** - Cumulative failed exports
8. **Export Rate by Format** - Exports per second over time
9. **Duration (p50/p95)** - Export latency percentiles
10. **Request/Response Sizes** - Document size trends
11. **Total Exports by Format** - Cumulative exports per format

## Prometheus Query Examples

### Export Rate (requests/sec)
```promql
rate(strictdoc_exports_total[5m])
```

### Error Rate (%)
```promql
rate(strictdoc_export_failures_total[5m]) / rate(strictdoc_exports_total[5m]) * 100
```

### P95 Response Time
```promql
histogram_quantile(0.95, rate(strictdoc_export_duration_seconds_bucket[5m]))
```

### Exports by Format
```promql
sum by (format) (strictdoc_exports_total)
```

## Configuration Files

### Prometheus Configuration
- File: `prometheus.yml`
- Scrape interval: 10 seconds
- Scrape timeout: 5 seconds

### Grafana Provisioning
- Datasources: `grafana/provisioning/datasources/`
- Dashboards: `grafana/provisioning/dashboards/`
- Dashboard JSON: `grafana/dashboards/strictdoc-service.json`

### Docker Compose
- File: `docker-compose.yml`
- Services: strictdoc-service, prometheus, grafana
- Networks: monitoring (bridge)
- Volumes: prometheus-data, grafana-data

## Troubleshooting

### Services not starting
```bash
# Check Docker logs
docker compose -f docker-compose.yml logs

# Check individual service
docker compose -f docker-compose.yml logs strictdoc-service
docker compose -f docker-compose.yml logs prometheus
docker compose -f docker-compose.yml logs grafana
```

### Metrics not appearing
1. Check Prometheus targets: http://localhost:9090/targets
2. Verify service is exposing metrics: http://localhost:9183/metrics
3. Check Grafana datasource configuration

### Dashboard not loading
1. Verify Grafana provisioning: `docker compose -f docker-compose.yml logs grafana`
2. Check dashboard exists: http://localhost:3000/dashboards
3. Reimport dashboard manually if needed

## Clean Up

### Stop services but keep data
```bash
./stop-monitoring.sh
# Choose 'N' when asked about removing volumes
```

### Stop services and remove all data
```bash
./stop-monitoring.sh
# Choose 'Y' when asked about removing volumes
```

### Manual cleanup
```bash
docker compose -f docker-compose.yml down -v
docker rmi strictdoc-service:dev
```

## Load Testing

Use the built-in load generator:
```bash
# Light load: 100 requests, 10 concurrent
./generate-load.sh

# Medium load: 500 requests, 20 concurrent
./generate-load.sh 500 20

# Heavy load: 2000 requests, 50 concurrent
./generate-load.sh 2000 50
```

## Access URLs Summary

| Service | URL | Credentials |
|---------|-----|-------------|
| StrictDoc Service | http://localhost:9083 | - |
| API Docs | http://localhost:9083/docs | - |
| Raw Metrics | http://localhost:9183/metrics | - |
| Prometheus | http://localhost:9090 | - |
| Grafana | http://localhost:3000 | admin/admin |
| Grafana Dashboard | http://localhost:3000/d/strictdoc-service | admin/admin |
