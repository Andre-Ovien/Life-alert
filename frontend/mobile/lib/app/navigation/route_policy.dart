import '../../core/access/preview_session.dart';
import 'catalog.dart';
import 'screen_spec.dart';

class RouteMatch {
  const RouteMatch(this.screen, this.parameters);
  final ScreenSpec screen;
  final Map<String, String> parameters;
}

RouteMatch? matchScreen(Uri uri) {
  final parts = uri.pathSegments;
  for (final screen in consumerScreens) {
    final pattern = Uri.parse(screen.path).pathSegments;
    if (pattern.length != parts.length) continue;
    final parameters = <String, String>{};
    var matches = true;
    for (var index = 0; index < parts.length; index++) {
      if (pattern[index].startsWith(':')) {
        parameters[pattern[index].substring(1)] = parts[index];
      } else if (pattern[index] != parts[index]) {
        matches = false;
        break;
      }
    }
    if (matches) return RouteMatch(screen, parameters);
  }
  return null;
}

bool canOpen(PreviewSession session, RouteMatch match) {
  final id = match.screen.id;
  final childId = match.parameters['childId'];
  if (childId != null && !session.childIds.contains(childId)) return false;
  switch (session.role) {
    case PreviewRole.linkedChild:
      return id.startsWith('C') && (session.deviceLinked || id == 'C01');
    case PreviewRole.signedOut:
      return id.startsWith('A');
    case PreviewRole.guardian:
      return !id.startsWith('C');
    case PreviewRole.caregiver:
      return session.caregiverScreenGrants.contains(id);
  }
}
