/// Preview personas are NOT authentication. Replace with vetted identity,
/// server-enforced grants and secure device credentials before live integration.
enum PreviewRole { signedOut, guardian, caregiver, linkedChild }

class PreviewSession {
  const PreviewSession({
    this.role = PreviewRole.signedOut,
    this.childIds = const {'preview-child'},
    this.caregiverScreenGrants = const {
      'G01',
      'F01',
      'F02',
      'I01',
      'I02',
      'I03',
      'I05',
      'I06',
      'I07',
      'S01',
      'S05',
    },
    this.deviceLinked = true,
  });
  final PreviewRole role;
  final Set<String> childIds;
  final Set<String> caregiverScreenGrants;
  final bool deviceLinked;
}
