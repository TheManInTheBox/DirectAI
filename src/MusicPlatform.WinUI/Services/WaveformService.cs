using Windows.Storage;
using Windows.Storage.Streams;
using System.Runtime.InteropServices.WindowsRuntime;

namespace MusicPlatform.WinUI.Services;

/// <summary>
/// Service for generating waveform visualization data from audio files
/// </summary>
public class WaveformService
{
    /// <summary>
    /// Generate waveform data points from an audio file
    /// </summary>
    /// <param name="audioFile">The audio file to analyze</param>
    /// <param name="sampleCount">Number of data points to generate (typically matches display width)</param>
    /// <returns>Array of normalized amplitude values (0.0 to 1.0)</returns>
    public async Task<float[]> GenerateWaveformAsync(StorageFile audioFile, int sampleCount = 500)
    {
        try
        {
            // Read audio file data
            using var stream = await audioFile.OpenReadAsync();
            var reader = new DataReader(stream);
            
            // Load all data
            var totalBytes = (uint)stream.Size;
            await reader.LoadAsync(totalBytes);
            
            // Read bytes
            var buffer = new byte[totalBytes];
            reader.ReadBytes(buffer);
            
            // Skip WAV header (44 bytes)
            var startOffset = 44;
            if (totalBytes < startOffset)
            {
                return new float[sampleCount];
            }
            
            // Calculate samples per waveform point
            var audioDataLength = buffer.Length - startOffset;
            var samplesPerPoint = Math.Max(1, audioDataLength / sampleCount / 2); // Divide by 2 for 16-bit audio
            
            var waveform = new float[sampleCount];
            
            for (int i = 0; i < sampleCount; i++)
            {
                var startPos = startOffset + (i * samplesPerPoint * 2);
                if (startPos + 2 >= buffer.Length)
                {
                    break;
                }
                
                // Read 16-bit sample (little-endian)
                var sample = (short)(buffer[startPos] | (buffer[startPos + 1] << 8));
                
                // Normalize to 0.0-1.0 range
                var normalized = Math.Abs(sample) / 32768.0f;
                waveform[i] = normalized;
            }
            
            // Smooth the waveform
            waveform = SmoothWaveform(waveform);
            
            return waveform;
        }
        catch (Exception ex)
        {
            System.Diagnostics.Debug.WriteLine($"Error generating waveform: {ex.Message}");
            return new float[sampleCount];
        }
    }
    
    /// <summary>
    /// Apply simple moving average smoothing to waveform data
    /// </summary>
    private float[] SmoothWaveform(float[] data, int windowSize = 3)
    {
        if (data.Length < windowSize)
        {
            return data;
        }
        
        var smoothed = new float[data.Length];
        
        for (int i = 0; i < data.Length; i++)
        {
            var sum = 0.0f;
            var count = 0;
            
            for (int j = -windowSize / 2; j <= windowSize / 2; j++)
            {
                var index = i + j;
                if (index >= 0 && index < data.Length)
                {
                    sum += data[index];
                    count++;
                }
            }
            
            smoothed[i] = sum / count;
        }
        
        return smoothed;
    }
    
    /// <summary>
    /// Generate waveform SVG path data for rendering
    /// </summary>
    /// <param name="waveform">Waveform data points</param>
    /// <param name="width">Display width in pixels</param>
    /// <param name="height">Display height in pixels</param>
    /// <returns>SVG path data string</returns>
    public string GenerateWaveformPath(float[] waveform, double width, double height)
    {
        if (waveform.Length == 0)
        {
            return "";
        }
        
        var pathData = new System.Text.StringBuilder();
        var pointSpacing = width / waveform.Length;
        var centerY = height / 2;
        
        // Start at first point
        pathData.Append($"M 0,{centerY} ");
        
        // Draw top half of waveform
        for (int i = 0; i < waveform.Length; i++)
        {
            var x = i * pointSpacing;
            var y = centerY - (waveform[i] * centerY * 0.8); // 0.8 for padding
            pathData.Append($"L {x:F1},{y:F1} ");
        }
        
        // Draw bottom half (mirrored)
        for (int i = waveform.Length - 1; i >= 0; i--)
        {
            var x = i * pointSpacing;
            var y = centerY + (waveform[i] * centerY * 0.8);
            pathData.Append($"L {x:F1},{y:F1} ");
        }
        
        pathData.Append("Z"); // Close path
        
        return pathData.ToString();
    }
}
