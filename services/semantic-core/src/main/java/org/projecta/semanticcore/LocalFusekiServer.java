package org.projecta.semanticcore;

import java.io.BufferedReader;
import java.io.IOException;
import java.io.InputStreamReader;
import java.nio.charset.StandardCharsets;
import java.nio.file.Path;
import java.util.concurrent.atomic.AtomicBoolean;
import org.apache.jena.fuseki.main.FusekiServer;

/** Runs the local TDB2-backed Fuseki service with a private stdin shutdown channel. */
public final class LocalFusekiServer {
    private LocalFusekiServer() {}

    public static void main(String[] args) throws InterruptedException {
        if (args.length != 2) {
            throw new IllegalArgumentException("expected <port> <configuration-file>");
        }
        int port = Integer.parseInt(args[0]);
        var server = FusekiServer.create()
                .loopback(true)
                .port(port)
                .parseConfigFile(Path.of(args[1]))
                .build();
        var stopped = new AtomicBoolean();
        Runnable stop = () -> {
            if (stopped.compareAndSet(false, true)) {
                server.stop();
            }
        };

        server.start();
        Runtime.getRuntime().addShutdownHook(new Thread(stop, "projecta-fuseki-shutdown"));
        var control = new Thread(() -> watchControlPipe(stop), "projecta-fuseki-control");
        control.setDaemon(true);
        control.start();
        server.join();
        stop.run();
    }

    private static void watchControlPipe(Runnable stop) {
        try (var input = new BufferedReader(new InputStreamReader(System.in, StandardCharsets.UTF_8))) {
            String command;
            while ((command = input.readLine()) != null) {
                if (command.equals("stop")) {
                    break;
                }
            }
        } catch (IOException ignored) {
            // The launcher owns the pipe; its loss must close TDB2 rather than leave a writer behind.
        } finally {
            stop.run();
        }
    }
}
