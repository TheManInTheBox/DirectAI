namespace MusicPlatform.Maui;

public partial class AppShell : Shell
{
	public AppShell()
	{
		InitializeComponent();
		
		// Register routes for navigation
		Routing.RegisterRoute("AudioFileDetailPage", typeof(Pages.AudioFileDetailPage));
		Routing.RegisterRoute("generation", typeof(Pages.GenerationPage));
	}
}
