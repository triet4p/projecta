package org.projecta.semanticcore;

import java.nio.charset.StandardCharsets;
import java.security.MessageDigest;
import java.security.NoSuchAlgorithmException;
import java.util.HexFormat;
import java.util.UUID;

/** Server-derived identifiers; client idempotency keys never become resource names. */
public final class OpaqueIds {
    private OpaqueIds() {}

    public static String random(String prefix) {
        return prefix + UUID.randomUUID();
    }

    public static String idempotencyDigest(String key) {
        try {
            var digest = MessageDigest.getInstance("SHA-256");
            return HexFormat.of().formatHex(digest.digest(key.getBytes(StandardCharsets.UTF_8)));
        } catch (NoSuchAlgorithmException exception) {
            throw new IllegalStateException("SHA-256 is unavailable", exception);
        }
    }
}
