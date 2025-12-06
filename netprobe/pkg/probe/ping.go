package probe

import (
	"fmt"
	"os/exec"
	"runtime"
	"strings"
)

func Ping(opts PingOptions) Result {
	toolName := opts.Tool
	if toolName == "" {
		toolName = "network.ping"
	}

	count := opts.Count
	if count <= 0 {
		count = 4
	}

	args := []string{}
	switch runtime.GOOS {
	case "windows":
		args = append(args, "-n", fmt.Sprintf("%d", count))
	default:
		args = append(args, "-c", fmt.Sprintf("%d", count))
		// 尽量设置每次请求超时（部分平台不支持 -W，则交由外部超时控制）
		if opts.TimeoutSec > 0 {
			args = append(args, "-W", fmt.Sprintf("%d", opts.TimeoutSec))
		}
	}
	args = append(args, opts.Target)

	cmdResult, err := RunCommand(opts.TimeoutSec, "ping", args...)

	result := Result{
		Tool:      toolName,
		Target:    opts.Target,
		Count:     count,
		RawOutput: "",
		Summary:   map[string]any{},
	}

	if cmdResult != nil {
		result.RawOutput = TrimOutput(cmdResult.Stdout, 8000)
	}

	// 提取关键行
	if cmdResult != nil {
		for _, line := range strings.Split(cmdResult.Stdout, "\n") {
			l := strings.TrimSpace(line)
			if l == "" {
				continue
			}
			if strings.Contains(strings.ToLower(l), "packet loss") || strings.Contains(l, "丢失") {
				result.Summary["packet_loss_line"] = l
			}
			if strings.Contains(strings.ToLower(l), "rtt") || strings.Contains(strings.ToLower(l), "round-trip") || strings.Contains(l, "往返行程") {
				result.Summary["rtt_line"] = l
			}
		}
	}

	if err == nil {
		result.Success = true
		return result
	}

	// 命令不存在的情况
	if _, ok := err.(*exec.Error); ok {
		result.Error = "ping command not found"
		return result
	}

	result.Error = err.Error()
	return result
}
