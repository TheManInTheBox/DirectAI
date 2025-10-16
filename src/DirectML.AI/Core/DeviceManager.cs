using System;
using System.Collections.Generic;
using System.Threading;
using System.Threading.Tasks;
using Microsoft.Extensions.Logging;
using DirectML.AI.DirectML;

namespace DirectML.AI.Core
{
    /// <summary>
    /// Manages DirectML devices and provides device selection capabilities
    /// </summary>
    public class DeviceManager : IDisposable
    {
        private readonly ILogger<DeviceManager> _logger;
        private readonly DirectMLDeviceManager _directMLDeviceManager;
        private bool _isInitialized;

        public DeviceManager(ILogger<DeviceManager> logger, ILoggerFactory loggerFactory)
        {
            _logger = logger;
            _directMLDeviceManager = new DirectMLDeviceManager(loggerFactory.CreateLogger<DirectMLDeviceManager>());
        }

        public bool IsInitialized => _isInitialized;
        public DirectMLDevice? SelectedDevice => _directMLDeviceManager.GetOptimalInferenceDevice();
        public IEnumerable<DirectMLDevice> AvailableDevices => 
            _directMLDeviceManager.EnumerateInferenceDevicesAsync().GetAwaiter().GetResult();

        public async Task<bool> InitializeAsync(DirectMLConfig config, CancellationToken cancellationToken = default)
        {
            try
            {
                _logger.LogInformation("Initializing device manager");

                var initialized = await _directMLDeviceManager.InitializeAsync();
                if (!initialized)
                {
                    _logger.LogError("Failed to initialize DirectML device manager");
                    return false;
                }

                _isInitialized = true;
                _logger.LogInformation("Device manager initialized with device {DeviceName}", 
                    SelectedDevice?.Description ?? "None");
                return true;
            }
            catch (Exception ex)
            {
                _logger.LogError(ex, "Failed to initialize device manager");
                return false;
            }
        }

        public async Task ShutdownAsync(CancellationToken cancellationToken = default)
        {
            try
            {
                _directMLDeviceManager.Dispose();
                _isInitialized = false;
                _logger.LogInformation("Device manager shut down");
            }
            catch (Exception ex)
            {
                _logger.LogError(ex, "Error during device manager shutdown");
            }
        }

        public void Dispose()
        {
            _directMLDeviceManager?.Dispose();
        }
    }
}
