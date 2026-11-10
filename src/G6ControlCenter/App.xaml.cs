using System.IO;
using System.Windows;
using System.Windows.Threading;

namespace G6ControlCenter;

public partial class App : Application
{
    private static readonly string LogDirectory = Path.Combine(
        Environment.GetFolderPath(Environment.SpecialFolder.LocalApplicationData),
        "G6ControlCenter", "Logs");

    private static readonly string LogFile = Path.Combine(LogDirectory, "startup.log");

    protected override void OnStartup(StartupEventArgs e)
    {
        DispatcherUnhandledException += OnDispatcherUnhandledException;
        AppDomain.CurrentDomain.UnhandledException += OnUnhandledException;

        WriteLog("------------------------------------------------------------");
        WriteLog($"Startup entered. Version={System.Reflection.Assembly.GetEntryAssembly()?.GetName().Version}");
        WriteLog($"OS={Environment.OSVersion}; 64-bit process={Environment.Is64BitProcess}");
        WriteLog("Using WPF StartupUri=MainWindow.xaml.");

        base.OnStartup(e);
    }

    protected override void OnExit(ExitEventArgs e)
    {
        WriteLog($"Application exiting. ExitCode={e.ApplicationExitCode}");
        base.OnExit(e);
    }

    private void OnDispatcherUnhandledException(object sender, DispatcherUnhandledExceptionEventArgs e)
    {
        WriteLog("DISPATCHER EXCEPTION: " + e.Exception);
        MessageBox.Show(
            $"An unexpected UI error occurred.\n\n{e.Exception.GetType().Name}: {e.Exception.Message}\n\nLog: {LogFile}",
            "G6 Control Center - UI Error",
            MessageBoxButton.OK,
            MessageBoxImage.Error);
        // Leave the exception unhandled so WPF does not continue in an unknown state.
        e.Handled = false;
    }

    private static void OnUnhandledException(object sender, UnhandledExceptionEventArgs e)
    {
        WriteLog("UNHANDLED APPDOMAIN EXCEPTION: " + e.ExceptionObject);
    }

    private static void WriteLog(string message)
    {
        try
        {
            Directory.CreateDirectory(LogDirectory);
            File.AppendAllText(LogFile, $"[{DateTimeOffset.Now:yyyy-MM-dd HH:mm:ssf zzz}] {message}{Environment.NewLine}");
        }
        catch
        {
            // Logging must never prevent the application from starting.
        }
    }
}
