using Windows.Storage;
using System.Text;
using NAudio.Wave;

namespace MusicPlatform.WinUI.Services;

/// <summary>
/// Real waveform service that generates authentic waveforms from actual audio data
/// No simulations - only real audio analysis
/// </summary>
public class FastWaveformService
{
    private readonly Dictionary<string, WaveformCache> _waveformCache = new();
    private readonly SemaphoreSlim _cacheLock = new(1, 1);

    /// <summary>
    /// Generate waveform from real audio file data
    /// </summary>
    public async Task<string> GenerateWaveformFromAudioAsync(StorageFile audioFile, int width = 800, int height = 80)
    {
        try
        {
            var cacheKey = $"waveform_{audioFile.Name}_{width}x{height}";
            
            await _cacheLock.WaitAsync();
            try
            {
                if (_waveformCache.ContainsKey(cacheKey))
                {
                    return _waveformCache[cacheKey].WaveformPath;
                }
            }
            finally
            {
                _cacheLock.Release();
            }

            // Read actual audio file and extract amplitude data
            var amplitudes = await ExtractAmplitudesFromAudioAsync(audioFile, width);
            var waveformPath = GenerateWaveformPathFromAmplitudes(amplitudes, width, height);
            
            await _cacheLock.WaitAsync();
            try
            {
                _waveformCache[cacheKey] = new WaveformCache
                {
                    WaveformPath = waveformPath,
                    CreatedAt = DateTime.UtcNow
                };
            }
            finally
            {
                _cacheLock.Release();
            }
            
            return waveformPath;
        }
        catch (Exception ex)
        {
            System.Diagnostics.Debug.WriteLine($"Error generating real waveform: {ex.Message}");
            return "";
        }
    }

    private async Task<List<float>> ExtractAmplitudesFromAudioAsync(StorageFile audioFile, int targetWidth)
    {
        try
        {
            System.Diagnostics.Debug.WriteLine($"=== EXTRACTING AMPLITUDES FROM: {audioFile.Path} ===");
            
            // Use NAudio to properly read audio file directly from path
            using var audioFileReader = new AudioFileReader(audioFile.Path);
            
            var sampleRate = audioFileReader.WaveFormat.SampleRate;
            var channels = audioFileReader.WaveFormat.Channels;
            var totalSamples = audioFileReader.Length / (audioFileReader.WaveFormat.BitsPerSample / 8);
            
            System.Diagnostics.Debug.WriteLine($"Audio format: {sampleRate}Hz, {channels} channels, {totalSamples} samples");
            
            // Calculate samples per pixel for downsampling
            var samplesPerPixel = Math.Max(1, (int)(totalSamples / channels / targetWidth));
            
            var amplitudes = new List<float>();
            var sampleBuffer = new float[samplesPerPixel * channels];
            
            for (int pixel = 0; pixel < targetWidth; pixel++)
            {
                int samplesRead = audioFileReader.Read(sampleBuffer, 0, sampleBuffer.Length);
                
                if (samplesRead == 0)
                    break;
                
                // Calculate RMS (Root Mean Square) for this pixel
                float sum = 0;
                int actualSamples = samplesRead / channels;
                
                for (int i = 0; i < samplesRead; i += channels)
                {
                    // Average all channels for this sample
                    float sampleValue = 0;
                    for (int ch = 0; ch < channels && i + ch < samplesRead; ch++)
                    {
                        sampleValue += Math.Abs(sampleBuffer[i + ch]);
                    }
                    sampleValue /= channels;
                    sum += sampleValue * sampleValue;
                }
                
                float rms = (float)Math.Sqrt(sum / actualSamples);
                amplitudes.Add(rms);
            }
            
            System.Diagnostics.Debug.WriteLine($"Extracted {amplitudes.Count} amplitude points");
            
            // Make sure we fill to target width if needed
            while (amplitudes.Count < targetWidth)
            {
                amplitudes.Add(0f);
            }
            
            return await Task.FromResult(amplitudes);
        }
        catch (Exception ex)
        {
            System.Diagnostics.Debug.WriteLine($"ERROR extracting amplitudes: {ex.Message}");
            System.Diagnostics.Debug.WriteLine($"Stack trace: {ex.StackTrace}");
            return Enumerable.Repeat(0f, targetWidth).ToList();
        }
    }

    private string GenerateWaveformPathFromAmplitudes(List<float> amplitudes, int width, int height)
    {
        if (amplitudes.Count == 0) return "";
        
        var pathBuilder = new StringBuilder();
        pathBuilder.Append($"M 0,{height / 2}");
        
        var maxAmplitude = amplitudes.Max();
        if (maxAmplitude == 0) maxAmplitude = 1; // Avoid division by zero
        
        // Top half of waveform
        for (int i = 0; i < amplitudes.Count; i++)
        {
            var x = (double)i / amplitudes.Count * width;
            var normalizedAmplitude = amplitudes[i] / maxAmplitude;
            var y = height / 2 * (1 - normalizedAmplitude);
            pathBuilder.Append($" L {x:F1},{y:F1}");
        }
        
        // Bottom half (mirror)
        for (int i = amplitudes.Count - 1; i >= 0; i--)
        {
            var x = (double)i / amplitudes.Count * width;
            var normalizedAmplitude = amplitudes[i] / maxAmplitude;
            var y = height / 2 * (1 + normalizedAmplitude);
            pathBuilder.Append($" L {x:F1},{y:F1}");
        }
        
        pathBuilder.Append(" Z");
        return pathBuilder.ToString();
    }

    public void ClearCache()
    {
        _waveformCache.Clear();
    }

    private class WaveformCache
    {
        public required string WaveformPath { get; set; }
        public DateTime CreatedAt { get; set; }
    }
}