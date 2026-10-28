using System.Windows;

namespace WerWarDas;

public partial class SettingsWindow : Window
{
    private readonly Settings _settings;

    public SettingsWindow(Settings settings)
    {
        InitializeComponent();
        _settings = settings.Clone();
        HostBox.Text = _settings.BrokerHost;
        PortBox.Text = _settings.BrokerPort.ToString();
        UserBox.Text = _settings.BrokerUser;
        PasswordBox.Password = _settings.BrokerPassword;
        PrefixBox.Text = _settings.TopicPrefix;
        PcNameBox.Text = _settings.PcName;
        ModeBox.SelectedIndex = _settings.Mode == ControlMode.Automatic ? 0 : 1;
        GraceBox.Text = _settings.GraceMinutes.ToString();
        ShutdownBox.Text = _settings.ShutdownAfterMinutes.ToString();
        AutostartBox.IsChecked = _settings.Autostart;
        RemovePinBox.IsEnabled = _settings.HasPin;
    }

    /// <summary>Die gespeicherten Einstellungen, wenn der Benutzer auf "Speichern" geklickt hat.</summary>
    public Settings? Result { get; private set; }

    private void Save_Click(object sender, RoutedEventArgs e)
    {
        if (string.IsNullOrWhiteSpace(HostBox.Text))
        {
            ErrorText.Text = "Bitte die Adresse von Home Assistant / dem MQTT-Broker eingeben.";
            return;
        }
        if (!int.TryParse(PortBox.Text, out var port) || port is < 1 or > 65535)
        {
            ErrorText.Text = "Ungültiger Port.";
            return;
        }
        if (!int.TryParse(GraceBox.Text, out var grace) || grace < 0
            || !int.TryParse(ShutdownBox.Text, out var shutdown) || shutdown < 0)
        {
            ErrorText.Text = "Bitte bei den Minuten nur ganze Zahlen ab 0 eingeben.";
            return;
        }

        _settings.BrokerHost = HostBox.Text.Trim();
        _settings.BrokerPort = port;
        _settings.BrokerUser = UserBox.Text.Trim();
        _settings.BrokerPassword = PasswordBox.Password;
        _settings.TopicPrefix = string.IsNullOrWhiteSpace(PrefixBox.Text) ? "werwardas" : PrefixBox.Text.Trim();
        _settings.PcName = string.IsNullOrWhiteSpace(PcNameBox.Text) ? System.Environment.MachineName : PcNameBox.Text.Trim();
        _settings.Mode = ModeBox.SelectedIndex == 0 ? ControlMode.Automatic : ControlMode.HomeAssistant;
        _settings.GraceMinutes = grace;
        _settings.ShutdownAfterMinutes = shutdown;
        _settings.Autostart = AutostartBox.IsChecked == true;
        if (RemovePinBox.IsChecked == true) _settings.SetPin("");
        else if (!string.IsNullOrEmpty(PinBox.Password)) _settings.SetPin(PinBox.Password);

        _settings.Save();
        Result = _settings;
        DialogResult = true;
    }
}
