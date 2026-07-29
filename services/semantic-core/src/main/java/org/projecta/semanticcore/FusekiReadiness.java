package org.projecta.semanticcore;

import java.net.http.HttpClient;
import java.net.http.HttpRequest;
import java.net.http.HttpResponse;
import java.time.Duration;

/** Checks whether the configured Fuseki server is accepting requests. */
public final class FusekiReadiness {
    private final HttpClient client;
    private final SemanticCoreConfiguration configuration;

    public FusekiReadiness(HttpClient client, SemanticCoreConfiguration configuration) {
        this.client = client;
        this.configuration = configuration;
    }

    public boolean isReady() {
        try {
            var request = HttpRequest.newBuilder(configuration.fusekiPingUrl())
                    .GET()
                    .timeout(Duration.ofSeconds(3))
                    .build();
            var response = client.send(request, HttpResponse.BodyHandlers.discarding());
            return response.statusCode() >= 200 && response.statusCode() < 300;
        } catch (Exception exception) {
            return false;
        }
    }
}
