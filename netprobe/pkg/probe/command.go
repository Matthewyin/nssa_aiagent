package probe

import (
	"bytes"
	"context"
	"os/exec"
	"strings"
	"time"
)

// CmdResult 保存子进程的输出。
type CmdResult struct {
	Stdout   string
	Stderr   string
	ExitCode int
	Duration time.Duration
}

// RunCommand 运行系统命令，带超时控制。
func RunCommand(timeoutSec int, name string, args ...string) (*CmdResult, error) {
	if timeoutSec <= 0 {
		timeoutSec = 60
	}
	ctx, cancel := context.WithTimeout(context.Background(), time.Duration(timeoutSec)*time.Second)
	defer cancel()

	cmd := exec.CommandContext(ctx, name, args...)
	var stdout, stderr bytes.Buffer
	cmd.Stdout = &stdout
	cmd.Stderr = &stderr

	start := time.Now()
	err := cmd.Run()
	duration := time.Since(start)

	result := &CmdResult{
		Stdout:   stdout.String(),
		Stderr:   stderr.String(),
		Duration: duration,
	}

	// 记录退出码
	if exitErr, ok := err.(*exec.ExitError); ok {
		result.ExitCode = exitErr.ExitCode()
	} else if err == nil {
		result.ExitCode = 0
	}

	// 如果是超时，Context 会返回错误
	if ctx.Err() == context.DeadlineExceeded {
		return result, ctx.Err()
	}

	if err != nil {
		return result, err
	}
	return result, nil
}

// TrimOutput 简单清理输出。
func TrimOutput(s string, limit int) string {
	s = strings.TrimSpace(s)
	if limit > 0 && len(s) > limit {
		return s[:limit] + "...(truncated)"
	}
	return s
}
