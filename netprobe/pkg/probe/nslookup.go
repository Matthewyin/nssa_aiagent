package probe

import (
	"context"
	"encoding/json"
	"net"
	"os/exec"
	"strings"
	"time"
)

func Nslookup(opts NslookupOptions) Result {
	toolName := opts.Tool
	if toolName == "" {
		toolName = "network.nslookup"
	}
	if opts.RecordType == "" {
		opts.RecordType = "A"
	}

	args := []string{}
	if opts.RecordType != "" && strings.ToUpper(opts.RecordType) != "A" {
		args = append(args, "-type="+opts.RecordType)
	}
	args = append(args, opts.Target)

	cmdResult, err := RunCommand(opts.TimeoutSec, "nslookup", args...)

	result := Result{
		Tool:       toolName,
		Target:     opts.Target,
		RecordType: strings.ToUpper(opts.RecordType),
		RawOutput:  "",
		Summary:    map[string]any{},
	}

	if cmdResult != nil {
		result.RawOutput = TrimOutput(cmdResult.Stdout, 8000)
	}

	if err == nil {
		result.Success = true
		return result
	}

	// nslookup 不存在时，尝试标准库解析
	if _, ok := err.(*exec.Error); ok {
		stdResult, stdErr := fallbackDNSLookup(result.RecordType, opts.Target, opts.TimeoutSec)
		if stdErr != nil {
			result.Error = stdErr.Error()
			return result
		}
		// fallback 结果放到 raw_output 里
		buf, _ := json.MarshalIndent(stdResult, "", "  ")
		result.RawOutput = string(buf)
		result.Success = true
		return result
	}

	result.Error = err.Error()
	return result
}

func fallbackDNSLookup(recordType, target string, timeoutSec int) (map[string]any, error) {
	if timeoutSec <= 0 {
		timeoutSec = 10
	}
	resolver := &net.Resolver{
		PreferGo: true,
	}
	ctx, cancel := context.WithTimeout(context.Background(), time.Duration(timeoutSec)*time.Second)
	defer cancel()

	recordType = strings.ToUpper(recordType)
	switch recordType {
	case "A":
		ips, err := resolver.LookupHost(ctx, target)
		if err != nil {
			return nil, err
		}
		return map[string]any{"A": ips}, nil
	case "AAAA":
		ips, err := resolver.LookupIP(ctx, "ip6", target)
		if err != nil {
			return nil, err
		}
		var list []string
		for _, ip := range ips {
			list = append(list, ip.String())
		}
		return map[string]any{"AAAA": list}, nil
	case "MX":
		records, err := resolver.LookupMX(ctx, target)
		if err != nil {
			return nil, err
		}
		var list []map[string]any
		for _, r := range records {
			list = append(list, map[string]any{"host": r.Host, "pref": r.Pref})
		}
		return map[string]any{"MX": list}, nil
	case "NS":
		records, err := resolver.LookupNS(ctx, target)
		if err != nil {
			return nil, err
		}
		var list []string
		for _, r := range records {
			list = append(list, r.Host)
		}
		return map[string]any{"NS": list}, nil
	case "TXT":
		txts, err := resolver.LookupTXT(ctx, target)
		if err != nil {
			return nil, err
		}
		return map[string]any{"TXT": txts}, nil
	case "CNAME":
		cname, err := resolver.LookupCNAME(ctx, target)
		if err != nil {
			return nil, err
		}
		return map[string]any{"CNAME": cname}, nil
	default:
		ips, err := resolver.LookupHost(ctx, target)
		if err != nil {
			return nil, err
		}
		return map[string]any{"A": ips}, nil
	}
}
