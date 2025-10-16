using Xunit;
using Microsoft.Extensions.DependencyInjection;
using Microsoft.Extensions.Logging;
using DirectML.AI.Core;
using DirectML.AI.Extensions;
using DirectML.AI.Inference;
using DirectML.AI.Models;

namespace DirectML.AI.Tests.Inference
{
    public class InferenceProviderTests
    {
        [Fact]
        public async Task InitializeAsync_ShouldSucceed()
        {
            // Arrange
            var services = new ServiceCollection();
            services.AddLogging();
            services.AddDirectMLInference();
            
            var serviceProvider = services.BuildServiceProvider();
            var inferenceProvider = serviceProvider.GetRequiredService<IInferenceProvider>();
            
            // Act
            var result = await inferenceProvider.InitializeAsync();
            
            // Assert
            Assert.True(result);
        }

        [Fact]
        public async Task LoadModelAsync_WithValidModel_ShouldSucceed()
        {
            // Arrange
            var services = new ServiceCollection();
            services.AddLogging();
            services.AddDirectMLInference();
            
            var serviceProvider = services.BuildServiceProvider();
            var inferenceProvider = serviceProvider.GetRequiredService<IInferenceProvider>();
            
            await inferenceProvider.InitializeAsync();
            
            var modelMetadata = new ModelMetadata(
                "test-model",
                "test-path.onnx", 
                "1.0",
                "transformer",
                1024,
                ".onnx");
            
            // Act
            var result = await inferenceProvider.LoadModelAsync(modelMetadata);
            
            // Assert
            Assert.True(result);
            Assert.True(inferenceProvider.IsModelLoaded);
            Assert.Equal(modelMetadata, inferenceProvider.LoadedModel);
        }

        [Fact]
        public async Task InferAsync_WithLoadedModel_ShouldReturnResponse()
        {
            // Arrange
            var services = new ServiceCollection();
            services.AddLogging();
            services.AddDirectMLInference();
            
            var serviceProvider = services.BuildServiceProvider();
            var inferenceProvider = serviceProvider.GetRequiredService<IInferenceProvider>();
            
            await inferenceProvider.InitializeAsync();
            
            var modelMetadata = new ModelMetadata(
                "test-model",
                "test-path.onnx",
                "1.0", 
                "transformer",
                1024,
                ".onnx");
            
            await inferenceProvider.LoadModelAsync(modelMetadata);
            
            var request = new InferenceRequest("Hello, world!");
            
            // Act
            var response = await inferenceProvider.InferAsync(request);
            
            // Assert
            Assert.NotNull(response);
            Assert.NotEmpty(response.Output);
            Assert.True(response.Confidence > 0);
            Assert.True(response.ProcessingTime > TimeSpan.Zero);
        }
    }
}
