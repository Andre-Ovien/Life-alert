/// Future authenticated, typed transport boundary. No HTTP implementation or
/// credential persistence is wired into the preview app.
abstract interface class ApiBoundary {
  Future<Map<String, Object?>> request(
    String method,
    String path, {
    Map<String, Object?>? body,
    String? idempotencyKey,
  });
}

class PreviewNetworkDisabled implements Exception {
  const PreviewNetworkDisabled();
  @override
  String toString() => 'Network disabled: this foundation sends no requests.';
}

class DisabledApiBoundary implements ApiBoundary {
  const DisabledApiBoundary();
  @override
  Future<Map<String, Object?>> request(
    String method,
    String path, {
    Map<String, Object?>? body,
    String? idempotencyKey,
  }) async {
    throw const PreviewNetworkDisabled();
  }
}
