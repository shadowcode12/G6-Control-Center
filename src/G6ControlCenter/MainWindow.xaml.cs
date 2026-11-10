using System.Windows;
using G6ControlCenter.ViewModels;

namespace G6ControlCenter;

public partial class MainWindow : Window
{
    private readonly MainViewModel _viewModel = new();

    public MainWindow()
    {
        InitializeComponent();
        DataContext = _viewModel;
    }

    private void Window_Loaded(object sender, RoutedEventArgs e) => _viewModel.Start();

    private void Window_Closed(object? sender, EventArgs e) => _viewModel.Dispose();
}
