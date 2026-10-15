# Life alert - Flutter structure preview

An actual Android/iOS Flutter foundation, created on the SSD using the installed Flutter 3.44.1 / Dart 3.12.1 SDK. No new SDK/Xcode installation was performed.

## What exists

- `lib/main.dart` and `app/life_alert_app.dart`: application entry/composition.
- `app/navigation/`: Flutter Router parser/delegate, consumer catalogue and demo route policy.
- `core/access/`: explicit preview personas and scoped-child/caregiver grant contracts.
- `core/api/`: typed integration interface with a disabled implementation. No HTTP client, production URL, credential or live provider is configured.
- `features/`: 10 grouped consumer feature catalogues matching the 46 screen IDs. Screen metadata uses one shared placeholder; 46 copied widget files are not created.
- `features/incidents/domain/`: request ID/payload and independent evidence contracts; travel copy requires en-route evidence. Provider receipt alone cannot produce it.
- `shared/presentation/`: reusable non-operational placeholder.
- Android/iOS runner projects with development preview bundle identifiers. No personal signing-team ID is embedded.

The three-dot preview menu changes DEMO PERSONA only. It is not sign-in or a production security boundary. A linked-child preview goes directly to C02 without adult authentication. Guardian/caregiver/child route separation and disallowed deep links are tested, but server object authorization remains essential before real integration. The preview contains no real family records, secrets or product actions. Selecting a screen opens documentation, never a help request, call, message or payment.

## Run and verify

From this directory:

```sh
flutter pub get
flutter analyze
flutter test
flutter build bundle --debug
```

For a manually chosen development target, `flutter run -d <device-id>` can run the preview after the human approves that device workflow. No app has been installed or launched on a phone during this task.

Validated: static analysis clean; 10 unit/widget/navigation tests pass; debug Dart asset bundle compiles. Tests cover route IDs, staff-route exclusion, foreign-child/caregiver/child restrictions, role-switch stack reset, direct child entry, revoked/unlinked child state, conservative status copy, disabled network and narrow-screen large text.

`flutter build bundle --debug` produces Dart/assets, **not an installable APK/IPA**. Android native build was not attempted: existing SDK reports licenses outstanding and references toolchains stored under another SSD project. Accept/review licenses and set up a project-owned toolchain before native release validation. iOS archive/device signing/build was not attempted. Chrome/web is unavailable and is outside the selected mobile scope. No license agreement was accepted or device deployment performed.

## Next steps after designer/client review

Replace shared placeholders feature by feature with approved layouts. Decide production adult identity, device pairing/secure storage, API decoding and offline relevance policy before real backend integration. Keep staff platform separate until selected. Do not wire billing, dialer, notifications or EMS into this preview. Further backend features require separate concrete authorization.

The complete designer screen list and source are linked from `../README.md`. Screen states are coverage requirements, not assumptions that each needs a new route or separately billed design.
