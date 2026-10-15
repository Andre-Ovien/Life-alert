import '../../features/adult_access/screen_catalog.dart';
import '../../features/home_readiness/screen_catalog.dart';
import '../../features/household/screen_catalog.dart';
import '../../features/child_profiles/screen_catalog.dart';
import '../../features/linked_devices/screen_catalog.dart';
import '../../features/care_media/screen_catalog.dart';
import '../../features/subscriptions/screen_catalog.dart';
import '../../features/incidents/screen_catalog.dart';
import '../../features/settings_support/screen_catalog.dart';
import '../../features/child_experience/screen_catalog.dart';
import 'screen_spec.dart';

const consumerScreens = <ScreenSpec>[
  ...adultAccessScreens,
  ...homeReadinessScreens,
  ...householdScreens,
  ...childProfilesScreens,
  ...linkedDevicesScreens,
  ...careMediaScreens,
  ...subscriptionsScreens,
  ...incidentsScreens,
  ...settingsSupportScreens,
  ...childExperienceScreens,
];
