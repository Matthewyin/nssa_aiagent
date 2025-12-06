package main

import (
	"encoding/json"
	"flag"
	"fmt"
	"os"
	"strings"

	"netprobe/pkg/probe"
)

func main() {
	if len(os.Args) < 2 {
		fmt.Fprintln(os.Stderr, usage())
		os.Exit(1)
	}

	cmd := os.Args[1]
	args := os.Args[2:]

	var res probe.Result
	var err error

	switch cmd {
	case "ping":
		fs := flag.NewFlagSet("ping", flag.ExitOnError)
		target := fs.String("target", "", "target host or ip")
		count := fs.Int("count", 4, "ping count")
		timeout := fs.Int("timeout", 10, "timeout seconds")
		_ = fs.Parse(args)
		if *target == "" {
			err = fmt.Errorf("target is required")
			break
		}
		res = probe.Ping(probe.PingOptions{
			Target:     *target,
			Count:      *count,
			TimeoutSec: *timeout,
			Tool:       "network.ping",
		})

	case "trace", "traceroute":
		fs := flag.NewFlagSet("trace", flag.ExitOnError)
		target := fs.String("target", "", "target host or ip")
		maxHops := fs.Int("max-hops", 30, "max hops")
		timeout := fs.Int("timeout", 60, "timeout seconds")
		_ = fs.Parse(args)
		if *target == "" {
			err = fmt.Errorf("target is required")
			break
		}
		res = probe.Traceroute(probe.TraceOptions{
			Target:     *target,
			MaxHops:    *maxHops,
			TimeoutSec: *timeout,
			Tool:       "network.traceroute",
		})

	case "mtr":
		fs := flag.NewFlagSet("mtr", flag.ExitOnError)
		target := fs.String("target", "", "target host or ip")
		count := fs.Int("count", 10, "probe count")
		reportCycles := fs.Int("report-cycles", 10, "report cycles")
		timeout := fs.Int("timeout", 60, "timeout seconds")
		_ = fs.Parse(args)
		if *target == "" {
			err = fmt.Errorf("target is required")
			break
		}
		res = probe.Mtr(probe.MtrOptions{
			Target:       *target,
			Count:        *count,
			ReportCycles: *reportCycles,
			TimeoutSec:   *timeout,
			Tool:         "network.mtr",
		})

	case "nslookup":
		fs := flag.NewFlagSet("nslookup", flag.ExitOnError)
		target := fs.String("target", "", "domain to query")
		recordType := fs.String("record-type", "A", "DNS record type")
		timeout := fs.Int("timeout", 10, "timeout seconds")
		_ = fs.Parse(args)
		if *target == "" {
			err = fmt.Errorf("target is required")
			break
		}
		res = probe.Nslookup(probe.NslookupOptions{
			Target:     *target,
			RecordType: *recordType,
			TimeoutSec: *timeout,
			Tool:       "network.nslookup",
		})

	case "tcp":
		fs := flag.NewFlagSet("tcp", flag.ExitOnError)
		host := fs.String("host", "", "target host")
		port := fs.Int("port", 0, "target port")
		timeout := fs.Int("timeout", 10, "timeout seconds")
		retry := fs.Int("retry", 0, "retry times")
		_ = fs.Parse(args)
		if *host == "" || *port == 0 {
			err = fmt.Errorf("host and port are required")
			break
		}
		res = probe.TCPProbe(probe.TCPOptions{
			Host:       *host,
			Port:       *port,
			TimeoutSec: *timeout,
			Retry:      *retry,
			Tool:       "network.tcp",
		})

	case "tls":
		fs := flag.NewFlagSet("tls", flag.ExitOnError)
		host := fs.String("host", "", "target host")
		port := fs.Int("port", 443, "target port")
		serverName := fs.String("server-name", "", "server name for SNI")
		timeout := fs.Int("timeout", 10, "timeout seconds")
		insecure := fs.Bool("insecure", false, "skip certificate verification")
		caCert := fs.String("ca-cert", "", "CA certificate path")
		clientCert := fs.String("client-cert", "", "client certificate path")
		clientKey := fs.String("client-key", "", "client key path")
		_ = fs.Parse(args)
		if *host == "" || *port == 0 {
			err = fmt.Errorf("host and port are required")
			break
		}
		res = probe.TLSProbe(probe.TLSOptions{
			Host:       *host,
			Port:       *port,
			ServerName: *serverName,
			TimeoutSec: *timeout,
			Insecure:   *insecure,
			CACert:     *caCert,
			ClientCert: *clientCert,
			ClientKey:  *clientKey,
			Tool:       "network.tls",
		})

	case "http":
		fs := flag.NewFlagSet("http", flag.ExitOnError)
		url := fs.String("url", "", "target url")
		method := fs.String("method", "GET", "http method")
		timeout := fs.Int("timeout", 15, "timeout seconds")
		expectStatus := fs.Int("expect-status", 0, "expected status code")
		expectContains := fs.String("expect-contains", "", "expected substring in body")
		body := fs.String("body", "", "request body")
		headersJSON := fs.String("headers", "", "headers as JSON object, e.g. {\"User-Agent\":\"netprobe\"}")
		headerKVs := multiString{}
		fs.Var(&headerKVs, "header", "single header in 'Key: Value' format (can repeat)")
		_ = fs.Parse(args)
		if *url == "" {
			err = fmt.Errorf("url is required")
			break
		}
		headers := map[string]string{}
		if *headersJSON != "" {
			if json.Unmarshal([]byte(*headersJSON), &headers) != nil {
				err = fmt.Errorf("invalid headers json")
				break
			}
		}
		for _, h := range headerKVs {
			parts := strings.SplitN(h, ":", 2)
			if len(parts) == 2 {
				headers[strings.TrimSpace(parts[0])] = strings.TrimSpace(parts[1])
			}
		}
		res = probe.HTTPProbe(probe.HTTPOptions{
			URL:            *url,
			Method:         *method,
			Headers:        headers,
			Body:           *body,
			TimeoutSec:     *timeout,
			ExpectStatus:   *expectStatus,
			ExpectContains: *expectContains,
			Tool:           "network.http",
		})

	default:
		err = fmt.Errorf("unknown subcommand: %s", cmd)
	}

	if err != nil {
		res = probe.Result{
			Success: false,
			Tool:    "network." + cmd,
			Error:   err.Error(),
		}
	}

	printJSON(res)
}

type multiString []string

func (m *multiString) String() string {
	return strings.Join(*m, ",")
}
func (m *multiString) Set(val string) error {
	*m = append(*m, val)
	return nil
}

func printJSON(res probe.Result) {
	data, err := json.MarshalIndent(res, "", "  ")
	if err != nil {
		fmt.Fprintf(os.Stderr, "marshal result failed: %v\n", err)
		os.Exit(1)
	}
	fmt.Println(string(data))
}

func usage() string {
	return `netprobe <subcommand> [options]

subcommands:
  ping         --target <host> [--count 4] [--timeout 10]
  trace        --target <host> [--max-hops 30] [--timeout 60]
  mtr          --target <host> [--count 10] [--report-cycles 10] [--timeout 60]
  nslookup     --target <domain> [--record-type A] [--timeout 10]
  tcp          --host <host> --port <port> [--timeout 10] [--retry 0]
  tls          --host <host> [--port 443] [--server-name <sni>] [--timeout 10] [--insecure] [--ca-cert path] [--client-cert path --client-key path]
  http         --url <url> [--method GET] [--timeout 15] [--expect-status <code>] [--expect-contains <str>] [--body <data>] [--headers <json>] [--header "K: V"]
`
}
