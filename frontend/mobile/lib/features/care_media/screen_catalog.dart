// Screen contracts only. All routes use shared non-operational placeholders.
import '../../app/navigation/screen_spec.dart';

const careMediaScreens = <ScreenSpec>[
  ScreenSpec(
    id: "M01",
    title: "Care recordings library",
    path: "/children/:childId/recordings",
    purpose: "Organize recordings by purpose and audience.",
    actions:
        "Filter comfort/instructions/both; open item; create recording; view text alternative.",
    states:
        "Empty; loading; upload pending; unauthorized audience; offline/unavailable audio.",
    phase: "M1",
    apiBoundary:
        "F: purpose metadata, text and authorized audio retrieval exist; mobile recorder/format work planned.",
  ),
  ScreenSpec(
    id: "M02",
    title: "Create a recording",
    path: "/children/:childId/recordings/new",
    purpose: "Capture or select safe care audio and label its purpose.",
    actions:
        "Request microphone when needed; record/review; provide text; select audiences; upload with progress.",
    states:
        "Mic denied; recording/paused; interrupted; upload retry/unknown; offline; invalid file.",
    phase: "M1",
    apiBoundary:
        "M: protected PCM WAV upload exists; native capture/conversion, offline queue and storage policy planned.",
  ),
  ScreenSpec(
    id: "M03",
    title: "Recording details + audience",
    path: "/children/:childId/recordings/:mediaId",
    purpose: "Review playback, text and explicit audience permissions.",
    actions:
        "Play/pause via shared player; edit title/text; change comfort/instruction/both access; review sharing impact.",
    states:
        "Loading; unavailable/revoked; permission changed; saving; playback interrupted.",
    phase: "M1",
    apiBoundary:
        "M: metadata/audience updates and private stream exist; deletion/retention request policy planned.",
  ),
];
