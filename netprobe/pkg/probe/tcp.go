package probe

import (
	"fmt"
	"net"
	"time"
)

func TCPProbe(opts TCPOptions) Result {
	toolName := opts.Tool
	if toolName == "" {
		toolName = "network.tcp"
	}
	if opts.TimeoutSec <= 0 {
		opts.TimeoutSec = 10
	}

	addr := fmt.Sprintf("%s:%d", opts.Host, opts.Port)

	var lastErr error
	var latency float64
	for attempt := 0; attempt <= opts.Retry; attempt++ {
		start := time.Now()
		conn, err := net.DialTimeout("tcp", addr, time.Duration(opts.TimeoutSec)*time.Second)
		if err == nil {
			latency = float64(time.Since(start).Milliseconds())
			_ = conn.Close()
			return Result{
				Success:   true,
				Tool:      toolName,
				Host:      opts.Host,
				Port:      opts.Port,
				LatencyMs: latency,
			}
		}
		lastErr = err
	}

	return Result{
		Success: false,
		Tool:    toolName,
		Host:    opts.Host,
		Port:    opts.Port,
		Error:   fmt.Sprintf("tcp dial failed: %v", lastErr),
	}
}
