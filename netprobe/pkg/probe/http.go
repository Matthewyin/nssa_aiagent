package probe

import (
	"bytes"
	"fmt"
	"io"
	"net/http"
	"strings"
	"time"
)

func HTTPProbe(opts HTTPOptions) Result {
	toolName := opts.Tool
	if toolName == "" {
		toolName = "network.http"
	}
	if opts.TimeoutSec <= 0 {
		opts.TimeoutSec = 15
	}
	method := strings.ToUpper(opts.Method)
	if method == "" {
		method = "GET"
	}

	var bodyReader io.Reader
	if opts.Body != "" {
		bodyReader = bytes.NewBufferString(opts.Body)
	}

	req, err := http.NewRequest(method, opts.URL, bodyReader)
	if err != nil {
		return Result{
			Success: false,
			Tool:    toolName,
			URL:     opts.URL,
			Error:   fmt.Sprintf("build request failed: %v", err),
		}
	}

	for k, v := range opts.Headers {
		req.Header.Set(k, v)
	}

	client := &http.Client{
		Timeout: time.Duration(opts.TimeoutSec) * time.Second,
	}

	start := time.Now()
	resp, err := client.Do(req)
	latency := time.Since(start)
	if err != nil {
		return Result{
			Success: false,
			Tool:    toolName,
			URL:     opts.URL,
			Error:   fmt.Sprintf("request failed: %v", err),
		}
	}
	defer resp.Body.Close()

	bodyBytes, _ := io.ReadAll(io.LimitReader(resp.Body, 4096))
	bodySnippet := string(bodyBytes)

	details := map[string]any{
		"response_headers": resp.Header,
		"body_snippet":     bodySnippet,
		"content_length":   resp.ContentLength,
	}

	var expectErr string
	if opts.ExpectStatus != 0 && resp.StatusCode != opts.ExpectStatus {
		expectErr = fmt.Sprintf("expect status %d, got %d", opts.ExpectStatus, resp.StatusCode)
	}
	if opts.ExpectContains != "" && !strings.Contains(bodySnippet, opts.ExpectContains) {
		if expectErr != "" {
			expectErr += "; "
		}
		expectErr += "response not contains expected substring"
	}

	success := expectErr == ""

	return Result{
		Success:    success,
		Tool:       toolName,
		URL:        opts.URL,
		StatusCode: resp.StatusCode,
		LatencyMs:  float64(latency.Milliseconds()),
		Details:    details,
		Error:      expectErr,
	}
}
