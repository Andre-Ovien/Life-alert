class ScreenSpec {
  const ScreenSpec({
    required this.id,
    required this.title,
    required this.path,
    required this.purpose,
    required this.actions,
    required this.states,
    required this.phase,
    required this.apiBoundary,
  });
  final String id;
  final String title;
  final String path;
  final String purpose;
  final String actions;
  final String states;
  final String phase;
  final String apiBoundary;

  String previewPath() => path.replaceAllMapped(RegExp(r':(\w+)'), (match) {
    return match[1] == 'childId' ? 'preview-child' : 'preview-${match[1]}';
  });
}
