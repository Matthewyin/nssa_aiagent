package probe

import (
	"fmt"
	"os/exec"
	"runtime"
)

func Traceroute(opts TraceOptions) Result {
	toolName := opts.Tool
	if toolName == "" {
		toolName = "network.traceroute"
	}
	if opts.MaxHops <= 0 {
		opts.MaxHops = 30
	}

	var cmd string
	var args []string

	switch runtime.GOOS {
	case "windows":
		cmd = "tracert"
		args = append(args, "-h", fmt.Sprintf("%d", opts.MaxHops))
	default:
		cmd = "traceroute"
		args = append(args, "-m", fmt.Sprintf("%d", opts.MaxHops))
		args = append(args, "-q", "1") // 少量探测，加快
		args = append(args, "-n")      // 不解析域名
	}
	args = append(args, opts.Target)

	cmdResult, err := RunCommand(opts.TimeoutSec, cmd, args...)

	result := Result{
		Tool:      toolName,
		Target:    opts.Target,
		MaxHops:   opts.MaxHops,
		RawOutput: "",
	}

	if cmdResult != nil {
		result.RawOutput = TrimOutput(cmdResult.Stdout, 8000)
	}

	if err == nil {
		result.Success = true
		return result
	}

	if _, ok := err.(*exec.Error); ok {
		result.Error = fmt.Sprintf("%s command not found", cmd)
		return result
	}

	result.Error = err.Error()
	return result
}
