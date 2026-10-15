/// Deliberately has no production URL, keys, live-provider flag or billing setup.
abstract final class AppConfig {
  static const previewOnly = true;
  static const warning =
      'DESIGN PREVIEW - No help requests, calls, payments or messages are sent.';
}
