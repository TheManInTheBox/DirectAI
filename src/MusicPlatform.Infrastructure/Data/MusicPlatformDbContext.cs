using Microsoft.EntityFrameworkCore;
using MusicPlatform.Domain.Models;

namespace MusicPlatform.Infrastructure.Data;

/// <summary>
/// Database context for the Music Platform. Supports both PostgreSQL (local) and SQL Server (Azure).
/// </summary>
public class MusicPlatformDbContext : DbContext
{
    public MusicPlatformDbContext(DbContextOptions<MusicPlatformDbContext> options)
        : base(options)
    {
    }

    // DbSets for all domain entities
    public DbSet<AudioFile> AudioFiles { get; set; }
    public DbSet<AnalysisResult> AnalysisResults { get; set; }
    public DbSet<JAMSAnnotation> JAMSAnnotations { get; set; }
    public DbSet<GenerationRequest> GenerationRequests { get; set; }
    public DbSet<GeneratedStem> GeneratedStems { get; set; }
    public DbSet<Job> Jobs { get; set; }
    public DbSet<Stem> Stems { get; set; }

    protected override void OnModelCreating(ModelBuilder modelBuilder)
    {
        base.OnModelCreating(modelBuilder);

        // AudioFile configuration
        modelBuilder.Entity<AudioFile>(entity =>
        {
            entity.HasKey(e => e.Id);
            entity.Property(e => e.OriginalFileName).IsRequired().HasMaxLength(500);
            entity.Property(e => e.BlobUri).IsRequired().HasMaxLength(2000);
            entity.Property(e => e.Format).IsRequired().HasMaxLength(20);
            entity.Property(e => e.Status).HasConversion<string>().IsRequired();
            entity.HasIndex(e => e.Status);
            entity.HasIndex(e => e.UploadedAt);
        });

        // AnalysisResult configuration
        modelBuilder.Entity<AnalysisResult>(entity =>
        {
            entity.HasKey(e => e.Id);
            entity.Property(e => e.MusicalKey).IsRequired().HasMaxLength(10);
            entity.Property(e => e.Mode).IsRequired().HasMaxLength(20);
            entity.OwnsMany(e => e.Sections, section =>
            {
                section.Property(s => s.Label).IsRequired().HasMaxLength(50);
            });
            entity.OwnsMany(e => e.Chords);
            entity.OwnsMany(e => e.Beats);
            
            // One-to-One relationship with AudioFile
            entity.HasOne<AudioFile>()
                  .WithOne()
                  .HasForeignKey<AnalysisResult>(e => e.AudioFileId)
                  .OnDelete(DeleteBehavior.Cascade);
            
            entity.HasIndex(e => e.AudioFileId);
            entity.HasIndex(e => e.AnalyzedAt);
        });

        // JAMSAnnotation configuration
        modelBuilder.Entity<JAMSAnnotation>(entity =>
        {
            entity.HasKey(e => e.Id);
            entity.Property(e => e.JamsJson).IsRequired();
            entity.Property(e => e.BlobUri).HasMaxLength(2000);
            
            // Many-to-One relationship with AudioFile
            entity.HasOne<AudioFile>()
                  .WithMany()
                  .HasForeignKey(e => e.AudioFileId)
                  .OnDelete(DeleteBehavior.Cascade);
            
            entity.HasIndex(e => e.AudioFileId);
            entity.HasIndex(e => e.CreatedAt);
        });

        // GenerationRequest configuration
        modelBuilder.Entity<GenerationRequest>(entity =>
        {
            entity.HasKey(e => e.Id);
            entity.Property(e => e.Status).HasConversion<string>().IsRequired();
            entity.OwnsOne(e => e.Parameters);
            
            // Many-to-One relationship with AudioFile
            entity.HasOne<AudioFile>()
                  .WithMany()
                  .HasForeignKey(e => e.AudioFileId)
                  .OnDelete(DeleteBehavior.Cascade);
            
            entity.HasIndex(e => e.AudioFileId);
            entity.HasIndex(e => e.Status);
            entity.HasIndex(e => e.RequestedAt);
        });

        // GeneratedStem configuration
        modelBuilder.Entity<GeneratedStem>(entity =>
        {
            entity.HasKey(e => e.Id);
            entity.Property(e => e.BlobUri).IsRequired().HasMaxLength(2000);
            entity.Property(e => e.Format).IsRequired().HasMaxLength(20);
            entity.Property(e => e.Type).HasConversion<string>().IsRequired();
            
            // Owned entity for metadata
            entity.OwnsOne(e => e.Metadata, metadata =>
            {
                metadata.Property(m => m.ModelName).HasMaxLength(100);
                metadata.Property(m => m.ModelVersion).HasMaxLength(50);
                // Store Dictionary as JSON
                metadata.Property(m => m.Conditioning)
                    .HasConversion(
                        v => System.Text.Json.JsonSerializer.Serialize(v, (System.Text.Json.JsonSerializerOptions?)null),
                        v => System.Text.Json.JsonSerializer.Deserialize<Dictionary<string, object>>(v, (System.Text.Json.JsonSerializerOptions?)null) ?? new Dictionary<string, object>()
                    );
            });
            
            // One-to-One relationship with GenerationRequest
            entity.HasOne<GenerationRequest>()
                  .WithOne()
                  .HasForeignKey<GeneratedStem>(e => e.GenerationRequestId)
                  .OnDelete(DeleteBehavior.Cascade);
            
            entity.HasIndex(e => e.GenerationRequestId);
            entity.HasIndex(e => e.GeneratedAt);
        });

        // Job configuration
        modelBuilder.Entity<Job>(entity =>
        {
            entity.HasKey(e => e.Id);
            entity.Property(e => e.Type).HasConversion<string>().IsRequired();
            entity.Property(e => e.Status).HasConversion<string>().IsRequired();
            entity.Property(e => e.OrchestrationInstanceId).HasMaxLength(200);
            
            // Store Dictionary as JSON
            entity.Property(e => e.Metadata)
                .HasConversion(
                    v => System.Text.Json.JsonSerializer.Serialize(v, (System.Text.Json.JsonSerializerOptions?)null),
                    v => System.Text.Json.JsonSerializer.Deserialize<Dictionary<string, object>>(v, (System.Text.Json.JsonSerializerOptions?)null) ?? new Dictionary<string, object>()
                );
            
            entity.HasIndex(e => e.EntityId);
            entity.HasIndex(e => e.Status);
            entity.HasIndex(e => e.StartedAt);
        });

        // Stem configuration
        modelBuilder.Entity<Stem>(entity =>
        {
            entity.HasKey(e => e.Id);
            entity.Property(e => e.Type).HasConversion<string>().IsRequired();
            entity.Property(e => e.BlobUri).IsRequired().HasMaxLength(2000);
            entity.Property(e => e.SourceSeparationModel).IsRequired().HasMaxLength(100);
            
            // Many-to-One relationship with AudioFile
            entity.HasOne<AudioFile>()
                  .WithMany()
                  .HasForeignKey(e => e.AudioFileId)
                  .OnDelete(DeleteBehavior.Cascade);
            
            entity.HasIndex(e => e.AudioFileId);
            entity.HasIndex(e => e.Type);
            entity.HasIndex(e => e.SeparatedAt);
        });
    }
}
