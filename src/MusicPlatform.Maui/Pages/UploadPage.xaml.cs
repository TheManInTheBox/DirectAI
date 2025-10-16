using MusicPlatform.Maui.ViewModels;

namespace MusicPlatform.Maui.Pages;

public partial class UploadPage : ContentPage
{
	public UploadPage(UploadViewModel viewModel)
	{
		InitializeComponent();
		BindingContext = viewModel;
	}
}
