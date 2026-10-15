enum DeliveryEvidence { localOnly, unconfirmed, received }

enum CrewEvidence { unassigned, offered, accepted, enRoute, arrived, complete }

enum EmsEvidence {
  pending,
  receiptOnly,
  unknown,
  contact,
  dispatch,
  arrived,
  closed,
}

class HelpRequest {
  const HelpRequest({
    required this.requestId,
    required this.childId,
    required this.location,
  });
  final String requestId;
  final String childId;

  /// Keep the original normalized payload with the ID for any retry.
  final Map<String, Object?>? location;
  Map<String, Object?> toJson() => {
    'request_id': requestId,
    'child': childId,
    if (location != null) 'location': location,
  };
}

class IncidentEvidence {
  const IncidentEvidence({
    this.delivery = DeliveryEvidence.localOnly,
    this.crew = CrewEvidence.unassigned,
    this.ems = EmsEvidence.pending,
    this.ownerClaimed = false,
    this.followupReview = false,
  });
  final DeliveryEvidence delivery;
  final CrewEvidence crew;
  final EmsEvidence ems;
  final bool ownerClaimed;
  final bool followupReview;

  String get message {
    if (delivery != DeliveryEvidence.received) {
      return 'Delivery is not confirmed.';
    }
    if (followupReview) {
      return 'New information needs coordinator review. A separate response is not confirmed.';
    }
    return switch (crew) {
      CrewEvidence.enRoute => 'Your response team is on the way.',
      CrewEvidence.arrived => 'Your response team has arrived.',
      CrewEvidence.accepted => 'A response team has accepted your request.',
      CrewEvidence.offered => 'We are contacting a response team.',
      _ =>
        ownerClaimed
            ? 'A coordinator is working on your request.'
            : 'Your request was received.',
    };
  }
}

abstract interface class IncidentRepository {
  Future<IncidentEvidence> requestHelp(HelpRequest request);
}
