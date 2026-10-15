import '../../../core/api/api_boundary.dart';
import '../domain/help_contract.dart';

/// Contract adapter only; the app uses DisabledApiBoundary. An acknowledgement
/// never fabricates crew or dispatch evidence; native/live mapping is deferred.
class DisabledIncidentRepository implements IncidentRepository {
  const DisabledIncidentRepository(this.api);
  final ApiBoundary api;
  @override
  Future<IncidentEvidence> requestHelp(HelpRequest request) async {
    await api.request(
      'POST',
      '/api/v1/incidents/help/',
      body: request.toJson(),
      idempotencyKey: request.requestId,
    );
    // A future real adapter must validate the actual payload, not assume success.
    throw const FormatException('Live incident decoding is not implemented.');
  }
}
