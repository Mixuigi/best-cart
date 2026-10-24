package by.mixuigi.golos;

import android.app.Notification;
import android.app.NotificationChannel;
import android.app.NotificationManager;
import android.app.PendingIntent;
import android.app.Service;
import android.content.Intent;
import android.content.pm.ServiceInfo;
import android.media.MediaMetadata;
import android.media.session.MediaSession;
import android.media.session.PlaybackState;
import android.net.wifi.WifiManager;
import android.os.IBinder;
import android.os.PowerManager;

/**
 * Фоновая служба с постоянным уведомлением. Пока она запущена, Android не замораживает
 * приложение и не отрезает ему сеть при выключенном экране (в том числе мобильный интернет),
 * а кнопки наушников приходят в нашу MediaSession.
 */
public class KeepAliveService extends Service {
    static final String CH = "golos";
    static final String STOP = "stop";
    static KeepAliveService inst;

    PowerManager.WakeLock wake;
    WifiManager.WifiLock wifi;
    MediaSession session;
    String title = "Слежу за кругами";

    @Override
    public void onCreate() {
        super.onCreate();
        inst = this;
        NotificationChannel ch = new NotificationChannel(CH, "Голос круга", NotificationManager.IMPORTANCE_LOW);
        ch.setShowBadge(false);
        getSystemService(NotificationManager.class).createNotificationChannel(ch);

        PowerManager pm = (PowerManager) getSystemService(POWER_SERVICE);
        wake = pm.newWakeLock(PowerManager.PARTIAL_WAKE_LOCK, "golos:keep");
        wake.acquire();
        WifiManager wm = (WifiManager) getApplicationContext().getSystemService(WIFI_SERVICE);
        wifi = wm.createWifiLock(WifiManager.WIFI_MODE_FULL_HIGH_PERF, "golos:wifi");
        wifi.acquire();

        session = new MediaSession(this, "golos");
        session.setCallback(new MediaSession.Callback() {
            @Override public void onPlay() { repeat(); }
            @Override public void onPause() { repeat(); }
            @Override public void onStop() { repeat(); }
            @Override public void onSkipToNext() { repeat(); }
            @Override public void onSkipToPrevious() { repeat(); }
        });
        session.setPlaybackState(new PlaybackState.Builder()
                .setActions(PlaybackState.ACTION_PLAY | PlaybackState.ACTION_PAUSE | PlaybackState.ACTION_PLAY_PAUSE
                        | PlaybackState.ACTION_STOP | PlaybackState.ACTION_SKIP_TO_NEXT | PlaybackState.ACTION_SKIP_TO_PREVIOUS)
                .setState(PlaybackState.STATE_PLAYING, 0, 1f)
                .build());
        session.setActive(true);
    }

    void repeat() {
        MainActivity a = MainActivity.live;
        if (a != null) a.repeatLast();
    }

    @Override
    public int onStartCommand(Intent intent, int flags, int startId) {
        if (intent != null && STOP.equals(intent.getAction())) {
            MainActivity a = MainActivity.live;
            if (a != null) a.finishAndRemoveTask();
            stopForeground(STOP_FOREGROUND_REMOVE);
            stopSelf();
            return START_NOT_STICKY;
        }
        if (android.os.Build.VERSION.SDK_INT >= 29)
            startForeground(1, build(), ServiceInfo.FOREGROUND_SERVICE_TYPE_MEDIA_PLAYBACK);
        else
            startForeground(1, build());
        return START_STICKY;
    }

    Notification build() {
        PendingIntent open = PendingIntent.getActivity(this, 0,
                new Intent(this, MainActivity.class).addFlags(Intent.FLAG_ACTIVITY_SINGLE_TOP),
                PendingIntent.FLAG_IMMUTABLE | PendingIntent.FLAG_UPDATE_CURRENT);
        PendingIntent stop = PendingIntent.getService(this, 1,
                new Intent(this, KeepAliveService.class).setAction(STOP), PendingIntent.FLAG_IMMUTABLE);
        return new Notification.Builder(this, CH)
                .setSmallIcon(R.drawable.ic_launcher)
                .setContentTitle(title)
                .setContentText("Голос круга работает в фоне")
                .setContentIntent(open)
                .setOngoing(true)
                .addAction(new Notification.Action.Builder(null, "Выключить", stop).build())
                .build();
    }

    /** Заголовок уведомления — последний круг, его видно на экране блокировки. */
    static void status(String t) {
        KeepAliveService s = inst;
        if (s == null || t == null) return;
        s.title = t;
        s.getSystemService(NotificationManager.class).notify(1, s.build());
        s.session.setMetadata(new MediaMetadata.Builder().putString(MediaMetadata.METADATA_KEY_TITLE, t).build());
    }

    @Override
    public void onDestroy() {
        inst = null;
        if (session != null) session.release();
        if (wake != null && wake.isHeld()) wake.release();
        if (wifi != null && wifi.isHeld()) wifi.release();
        super.onDestroy();
    }

    @Override
    public IBinder onBind(Intent intent) {
        return null;
    }
}
