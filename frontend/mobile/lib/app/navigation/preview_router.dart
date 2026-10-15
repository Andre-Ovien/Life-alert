import 'package:flutter/foundation.dart';
import 'package:flutter/material.dart';
import '../../core/access/preview_session.dart';
import '../../core/config/app_config.dart';
import '../../shared/presentation/screen_placeholder.dart';
import 'catalog.dart';
import 'route_policy.dart';

class PreviewPathParser extends RouteInformationParser<Uri> {
  const PreviewPathParser();
  @override
  Future<Uri> parseRouteInformation(RouteInformation routeInformation) =>
      SynchronousFuture(routeInformation.uri);
  @override
  RouteInformation restoreRouteInformation(Uri configuration) =>
      RouteInformation(uri: configuration);
}

class PreviewRouter extends RouterDelegate<Uri>
    with ChangeNotifier, PopNavigatorRouterDelegateMixin<Uri> {
  PreviewRouter({PreviewSession? session})
    : _session = session ?? const PreviewSession();
  PreviewSession _session;
  PreviewSession get session => _session;
  RouteMatch? selected;
  String? blockedReason;
  Uri _uri = Uri(path: '/preview');
  @override
  final GlobalKey<NavigatorState> navigatorKey = GlobalKey<NavigatorState>();
  @override
  Uri get currentConfiguration => _uri;

  void setSession(PreviewSession value) {
    _session = value;
    selected = null;
    blockedReason = null;
    _uri = Uri(path: '/preview');
    if (value.role == PreviewRole.linkedChild) {
      open(Uri(path: value.deviceLinked ? '/child/home' : '/child/activate'));
    } else {
      notifyListeners();
    }
  }

  void open(Uri uri) {
    blockedReason = null;
    if (uri.path == '/' || uri.path == '/preview') {
      selected = null;
      _uri = Uri(path: '/preview');
    } else {
      final match = matchScreen(uri);
      if (match == null || !canOpen(_session, match)) {
        selected = null;
        _uri = Uri(path: '/preview');
        blockedReason =
            'Preview access denied or route unavailable. Staff routes belong to a separate future surface.';
      } else {
        selected = match;
        _uri = uri;
      }
    }
    notifyListeners();
  }

  @override
  Future<void> setNewRoutePath(Uri configuration) {
    open(configuration);
    return SynchronousFuture(null);
  }

  @override
  Widget build(BuildContext context) => Navigator(
    key: navigatorKey,
    pages: [
      MaterialPage<void>(
        key: const ValueKey('preview-root'),
        child: _frame(context, _catalog(context)),
      ),
      if (selected case final match?)
        MaterialPage<void>(
          key: ValueKey(match.screen.id),
          child: _frame(context, ScreenPlaceholder(screen: match.screen)),
        ),
    ],
    onDidRemovePage: (page) {
      if (selected != null) {
        selected = null;
        _uri = Uri(path: '/preview');
        notifyListeners();
      }
    },
  );

  Widget _frame(BuildContext context, Widget body) => Scaffold(
    appBar: AppBar(
      title: const Text('Life alert - preview'),
      actions: [
        PopupMenuButton<PreviewRole>(
          tooltip: 'Demo persona - not authentication',
          onSelected: (role) => setSession(PreviewSession(role: role)),
          itemBuilder: (context) => PreviewRole.values
              .map((role) => PopupMenuItem(value: role, child: Text(role.name)))
              .toList(),
        ),
      ],
    ),
    body: SafeArea(
      child: Column(
        children: [
          Container(
            width: double.infinity,
            color: Theme.of(context).colorScheme.errorContainer,
            padding: const EdgeInsets.all(12),
            child: const Text(
              AppConfig.warning,
              style: TextStyle(fontSize: 12),
            ),
          ),
          Expanded(child: body),
        ],
      ),
    ),
  );

  Widget _catalog(BuildContext context) {
    final allowed = consumerScreens
        .where(
          (screen) =>
              canOpen(session, matchScreen(Uri.parse(screen.previewPath()))!),
        )
        .toList();
    return ListView(
      padding: const EdgeInsets.all(16),
      children: [
        if (blockedReason != null) ...[
          Text(blockedReason!, key: const ValueKey('access-denied')),
          const SizedBox(height: 16),
        ],
        const Text(
          'Route catalogue only - no finished UI or functioning service.',
        ),
        const SizedBox(height: 12),
        for (final screen in allowed)
          ListTile(
            key: ValueKey('route-${screen.id}'),
            title: Text('${screen.id} - ${screen.title}'),
            subtitle: Text('${screen.phase} / ${screen.path}'),
            onTap: () => open(Uri.parse(screen.previewPath())),
          ),
      ],
    );
  }
}
