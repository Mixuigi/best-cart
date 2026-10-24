package by.mixuigi.golos;

import android.Manifest;
import android.app.Activity;
import android.content.Intent;
import android.content.pm.PackageManager;
import android.net.Uri;
import android.os.Build;
import android.os.Bundle;
import android.os.PowerManager;
import android.provider.Settings;
import android.speech.tts.TextToSpeech;
import android.webkit.JavascriptInterface;
import android.webkit.RenderProcessGoneDetail;
import android.webkit.WebChromeClient;
import android.webkit.WebResourceRequest;
import android.webkit.WebSettings;
import android.webkit.WebView;
import android.webkit.WebViewClient;

import java.util.Locale;

/**
 * Обёртка над сайтом «Голос круга»: вся логика живёт на странице (GitHub Pages),
 * приложение только держит её живой при выключенном экране через KeepAliveService.
 */
public class MainActivity extends Activity {
    static final String URL = "https://mixuigi.github.io/best-cart/voice/";
    static MainActivity live;

    WebView web;
    TextToSpeech tts;

    @Override
    protected void onCreate(Bundle saved) {
        super.onCreate(saved);
        live = this;

        web = new WebView(this);
        setContentView(web);
        WebSettings s = web.getSettings();
        s.setJavaScriptEnabled(true);
        s.setDomStorageEnabled(true);
        s.setMediaPlaybackRequiresUserGesture(false);
        // не даём системе убить процесс страницы, когда приложение свёрнуто
        web.setRendererPriorityPolicy(WebView.RENDERER_PRIORITY_IMPORTANT, false);
        web.addJavascriptInterface(new Bridge(), "GolosApp");
        web.setWebChromeClient(new WebChromeClient());
        web.setWebViewClient(new WebViewClient() {
            @Override
            public boolean shouldOverrideUrlLoading(WebView v, WebResourceRequest r) {
                Uri u = r.getUrl();
                if ("mixuigi.github.io".equals(u.getHost())) return false;
                startActivity(new Intent(Intent.ACTION_VIEW, u));
                return true;
            }

            @Override
            public boolean onRenderProcessGone(WebView v, RenderProcessGoneDetail d) {
                recreate();
                return true;
            }
        });
        // метка в адресе — чтобы после правок сайта не показывать закэшированную страницу (Pages кэширует 10 мин)
        if (saved == null) web.loadUrl(URL + "?v=" + System.currentTimeMillis());
        else web.restoreState(saved);

        tts = new TextToSpeech(this, st -> {
            if (st == TextToSpeech.SUCCESS) tts.setLanguage(new Locale("ru", "RU"));
        });

        askPermissions();
        startForegroundService(new Intent(this, KeepAliveService.class));
    }

    void askPermissions() {
        if (Build.VERSION.SDK_INT >= 33
                && checkSelfPermission(Manifest.permission.POST_NOTIFICATIONS) != PackageManager.PERMISSION_GRANTED)
            requestPermissions(new String[]{Manifest.permission.POST_NOTIFICATIONS}, 1);
        PowerManager pm = (PowerManager) getSystemService(POWER_SERVICE);
        if (!pm.isIgnoringBatteryOptimizations(getPackageName())) {
            try {
                startActivity(new Intent(Settings.ACTION_REQUEST_IGNORE_BATTERY_OPTIMIZATIONS,
                        Uri.parse("package:" + getPackageName())));
            } catch (Exception ignored) {
            }
        }
    }

    /** Кнопка на наушниках → повтор последнего круга на странице. */
    void repeatLast() {
        runOnUiThread(() -> web.evaluateJavascript("window.repeatLast && repeatLast()", null));
    }

    @Override
    protected void onSaveInstanceState(Bundle out) {
        super.onSaveInstanceState(out);
        web.saveState(out);
    }

    // onPause/onStop намеренно не трогают WebView: pauseTimers() остановил бы страницу в кармане

    @Override
    public void onBackPressed() {
        if (web.canGoBack()) web.goBack();
        else moveTaskToBack(true);
    }

    @Override
    protected void onDestroy() {
        if (live == this) live = null;
        if (isFinishing()) stopService(new Intent(this, KeepAliveService.class));
        if (tts != null) tts.shutdown();
        web.destroy();
        super.onDestroy();
    }

    class Bridge {
        @JavascriptInterface
        public void speak(String text) {
            if (tts != null) tts.speak(text, TextToSpeech.QUEUE_ADD, null, "g" + System.nanoTime());
        }

        @JavascriptInterface
        public void stopSpeak() {
            if (tts != null) tts.stop();
        }

        @JavascriptInterface
        public void setStatus(String title) {
            KeepAliveService.status(title);
        }
    }
}
