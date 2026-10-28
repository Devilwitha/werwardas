using System;
using System.Threading;
using System.Windows;
using System.Windows.Threading;

namespace WerWarDas;

public partial class App : Application
{
    private Mutex? _singleInstance;
    private MqttService? _mqtt;
    private Controller? _controller;
    private TrayIcon? _tray;

    public static new App Current => (App)Application.Current;
    public static Settings Settings { get; private set; } = new();

    protected override void OnStartup(StartupEventArgs e)
    {
        base.OnStartup(e);

        _singleInstance = new Mutex(true, @"Local\WerWarDas.SingleInstance", out var isNew);
        if (!isNew)
        {
            MessageBox.Show("WerWarDas läuft bereits (siehe Symbol unten rechts in der Taskleiste).", "WerWarDas");
            Shutdown();
            return;
        }

        DispatcherUnhandledException += OnUnhandledException;
        Log.Write("WerWarDas gestartet");

        var firstStart = !Settings.Exists;
        Settings = Settings.Load();
        if (firstStart)
        {
            var dlg = new SettingsWindow(Settings);
            if (dlg.ShowDialog() != true || dlg.Result == null)
            {
                Shutdown();
                return;
            }
            Settings = dlg.Result;
        }

        StartServices();
    }

    private void StartServices()
    {
        _mqtt = new MqttService(Settings);
        _controller = new Controller(Settings, _mqtt, Dispatcher);
        _tray ??= new TrayIcon(_controller);
        _mqtt.Start();
    }

    private void StopServices()
    {
        _controller?.Stop();
        _tray?.Dispose();
        _tray = null;
        _mqtt?.Dispose();
        _mqtt = null;
        _controller = null;
    }

    public void OpenSettings()
    {
        if (_controller?.State == PcState.Locked) return;
        if (!PinDialog.Ask(Settings, "die Einstellungen zu öffnen")) return;
        var dlg = new SettingsWindow(Settings);
        if (dlg.ShowDialog() == true && dlg.Result != null)
        {
            Settings = dlg.Result;
            StopServices();
            StartServices();
        }
    }

    public void RequestExit()
    {
        if (_controller?.State == PcState.Locked) return;
        if (!PinDialog.Ask(Settings, "WerWarDas zu beenden")) return;
        StopServices();
        Log.Write("WerWarDas beendet");
        Shutdown();
    }

    private void OnUnhandledException(object sender, DispatcherUnhandledExceptionEventArgs e)
    {
        Log.Write($"Unbehandelter Fehler: {e.Exception}");
        e.Handled = true; // App weiterlaufen lassen
    }

    protected override void OnExit(ExitEventArgs e)
    {
        _mqtt?.Dispose();
        _singleInstance?.Dispose();
        base.OnExit(e);
    }
}
