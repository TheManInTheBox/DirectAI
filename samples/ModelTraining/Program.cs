using System;
using System.Threading.Tasks;
using Microsoft.Extensions.DependencyInjection;
using Microsoft.Extensions.Hosting;
using Microsoft.Extensions.Logging;
using DirectML.AI.Core;
using DirectML.AI.Extensions;

namespace ModelTraining
{
    class Program
    {
        static async Task Main(string[] args)
        {
            Console.WriteLine("DirectML.AI Model Training Sample");
            Console.WriteLine("=================================");

            // Create host with DirectML.AI services
            var builder = Host.CreateApplicationBuilder(args);
            
            builder.Services.AddDirectMLAI(config =>
            {
                config.DirectML.Enabled = true;
                config.Training.OutputDirectory = "training_output";
                config.Training.DefaultBatchSize = 8;
                config.Training.DefaultEpochs = 3;
            });

            var host = builder.Build();

            try
            {
                // Get services
                var aiService = host.Services.GetRequiredService<IAIService>();

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
                Console.WriteLine("Model training functionality will be implemented in future versions.");

                // Cleanup
                await aiService.ShutdownAsync();
                Console.WriteLine("Sample completed successfully!");
            }
            catch (Exception ex)
            {
                Console.WriteLine($"Error: {ex.Message}");
            }

            Console.WriteLine("Press any key to exit...");
            Console.ReadKey();
        }
    }
}
