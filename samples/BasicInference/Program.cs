using System;
using System.Collections.Generic;
using System.Threading.Tasks;
using Microsoft.Extensions.DependencyInjection;
using Microsoft.Extensions.Hosting;
using Microsoft.Extensions.Logging;
using DirectML.AI.Core;
using DirectML.AI.Extensions;
using DirectML.AI.Inference;
using DirectML.AI.Models;
using DirectML.AI.DirectML;

namespace BasicInference
{
    class Program
    {
        static async Task Main(string[] args)
        {
            Console.WriteLine("DirectML.AI Basic Inference Sample");
            Console.WriteLine("==================================");

            // Create host with DirectML.AI services
            var builder = Host.CreateApplicationBuilder(args);
            
            builder.Services.AddDirectMLAI(config =>
            {
                config.DirectML.Enabled = true;
                config.DirectML.DeviceId = 0;
                config.Models.CacheDirectory = "models";
                config.Models.EnableCache = true;
            });

            var host = builder.Build();

            try
            {
                // Get services
                var aiService = host.Services.GetRequiredService<IAIService>();
                var inferenceProvider = host.Services.GetRequiredService<IInferenceProvider>();
                var deviceManager = host.Services.GetRequiredService<DeviceManager>();

                // Initialize AI service
                Console.WriteLine("Initializing AI service...");
                var aiConfig = new AIConfiguration();
                var initialized = await aiService.InitializeAsync(aiConfig);
                
                if (!initialized)
                {
                    Console.WriteLine("Failed to initialize AI service");
                    return;
                }

                Console.WriteLine("AI service initialized successfully");

                // Display DirectML device information
                Console.WriteLine("\n--- DirectML Device Information ---");
                if (deviceManager.SelectedDevice != null)
                {
                    var device = deviceManager.SelectedDevice;
                    Console.WriteLine($"Selected Device: {device.Description}");
                    Console.WriteLine($"Device Type: {device.DeviceType}");
                    Console.WriteLine($"Dedicated Memory: {device.DedicatedVideoMemory / (1024 * 1024 * 1024)} GB");
                    Console.WriteLine($"Shared Memory: {device.SharedSystemMemory / (1024 * 1024 * 1024)} GB");
                    Console.WriteLine($"Vendor ID: 0x{device.VendorId:X4}");
                }
                else
                {
                    Console.WriteLine("No DirectML device selected");
                }

                // List all available devices
                Console.WriteLine("\n--- Available DirectML Devices ---");
                int deviceIndex = 0;
                foreach (var device in deviceManager.AvailableDevices)
                {
                    Console.WriteLine($"Device {deviceIndex}: {device.Description} ({device.DeviceType})");
                    deviceIndex++;
                }

                // Create a sample model metadata (in real usage, this would come from actual model files)
                var modelMetadata = new ModelMetadata(
                    Name: "sample-model",
                    Path: "sample-model.onnx",
                    Version: "1.0.0",
                    Architecture: "transformer", 
                    SizeBytes: 1024 * 1024, // 1MB
                    Format: ".onnx",
                    Properties: new Dictionary<string, object>
                    {
                        ["description"] = "Sample model for testing",
                        ["domain"] = "text-generation"
                    });

                // Load model
                Console.WriteLine($"\nLoading model: {modelMetadata.Name}");
                var modelLoaded = await inferenceProvider.LoadModelAsync(modelMetadata);
                
                if (!modelLoaded)
                {
                    Console.WriteLine("Failed to load model");
                    return;
                }

                Console.WriteLine("Model loaded successfully");

                // Run inference
                var inputs = new[]
                {
                    "Hello, how are you today?",
                    "What is artificial intelligence?",
                    "Explain machine learning in simple terms."
                };

                foreach (var input in inputs)
                {
                    Console.WriteLine($"\nInput: {input}");
                    Console.WriteLine("Processing...");

                    var request = new InferenceRequest(input, Options: new InferenceOptions(MaxTokens: 100));
                    var response = await inferenceProvider.InferAsync(request);

                    Console.WriteLine($"Output: {response.Output}");
                    Console.WriteLine($"Confidence: {response.Confidence:F2}");
                    Console.WriteLine($"Processing Time: {response.ProcessingTime.TotalMilliseconds:F0}ms");
                    
                    // Display device info from metadata
                    if (response.Metadata != null && response.Metadata.ContainsKey("device"))
                    {
                        Console.WriteLine($"Device Used: {response.Metadata["device"]}");
                    }
                }

                // Demonstrate streaming inference
                Console.WriteLine("\n--- Streaming Inference Demo ---");
                var streamInput = "Generate a short story about a robot";
                Console.WriteLine($"Stream Input: {streamInput}");
                Console.Write("Streaming Output: ");

                var streamRequest = new InferenceRequest(streamInput, Options: new InferenceOptions(Stream: true));
                await foreach (var chunk in inferenceProvider.InferStreamAsync(streamRequest))
                {
                    Console.Write($"{chunk.Output} ");
                    await Task.Delay(50); // Small delay to visualize streaming
                }
                Console.WriteLine();

                // Display statistics
                var stats = inferenceProvider.Statistics;
                Console.WriteLine($"\n--- Inference Statistics ---");
                Console.WriteLine($"Total Inferences: {stats.TotalInferences}");
                Console.WriteLine($"Average Processing Time: {stats.AverageProcessingTime.TotalMilliseconds:F0}ms");
                Console.WriteLine($"Total Tokens Generated: {stats.TotalTokensGenerated}");
                Console.WriteLine($"Last Inference: {stats.LastInference}");

                // Cleanup
                await inferenceProvider.UnloadModelAsync();
                await aiService.ShutdownAsync();

                Console.WriteLine("\nSample completed successfully!");
            }
            catch (Exception ex)
            {
                Console.WriteLine($"Error: {ex.Message}");
                Console.WriteLine($"Stack trace: {ex.StackTrace}");
            }

            Console.WriteLine("\nPress any key to exit...");
            Console.ReadKey();
        }
    }
}
