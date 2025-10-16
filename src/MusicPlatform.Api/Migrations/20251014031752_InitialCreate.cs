using System;
using System.Collections.Generic;
using Microsoft.EntityFrameworkCore.Migrations;

#nullable disable

namespace MusicPlatform.Api.Migrations
{
    /// <inheritdoc />
    public partial class InitialCreate : Migration
    {
        /// <inheritdoc />
        protected override void Up(MigrationBuilder migrationBuilder)
        {
            migrationBuilder.CreateTable(
                name: "AudioFiles",
                columns: table => new
                {
                    Id = table.Column<Guid>(type: "uuid", nullable: false),
                    OriginalFileName = table.Column<string>(type: "character varying(500)", maxLength: 500, nullable: false),
                    BlobUri = table.Column<string>(type: "character varying(2000)", maxLength: 2000, nullable: false),
                    SizeBytes = table.Column<long>(type: "bigint", nullable: false),
                    Duration = table.Column<TimeSpan>(type: "interval", nullable: false),
                    Format = table.Column<string>(type: "character varying(20)", maxLength: 20, nullable: false),
                    UploadedAt = table.Column<DateTime>(type: "timestamp with time zone", nullable: false),
                    Status = table.Column<string>(type: "text", nullable: false),
                    UserId = table.Column<string>(type: "text", nullable: true)
                },
                constraints: table =>
                {
                    table.PrimaryKey("PK_AudioFiles", x => x.Id);
                });

            migrationBuilder.CreateTable(
                name: "Jobs",
                columns: table => new
                {
                    Id = table.Column<Guid>(type: "uuid", nullable: false),
                    Type = table.Column<string>(type: "text", nullable: false),
                    EntityId = table.Column<Guid>(type: "uuid", nullable: false),
                    OrchestrationInstanceId = table.Column<string>(type: "character varying(200)", maxLength: 200, nullable: false),
                    Status = table.Column<string>(type: "text", nullable: false),
                    StartedAt = table.Column<DateTime>(type: "timestamp with time zone", nullable: false),
                    CompletedAt = table.Column<DateTime>(type: "timestamp with time zone", nullable: true),
                    ErrorMessage = table.Column<string>(type: "text", nullable: true),
                    Metadata = table.Column<string>(type: "text", nullable: false)
                },
                constraints: table =>
                {
                    table.PrimaryKey("PK_Jobs", x => x.Id);
                });

            migrationBuilder.CreateTable(
                name: "AnalysisResults",
                columns: table => new
                {
                    Id = table.Column<Guid>(type: "uuid", nullable: false),
                    AudioFileId = table.Column<Guid>(type: "uuid", nullable: false),
                    Bpm = table.Column<float>(type: "real", nullable: false),
                    MusicalKey = table.Column<string>(type: "character varying(10)", maxLength: 10, nullable: false),
                    Mode = table.Column<string>(type: "character varying(20)", maxLength: 20, nullable: false),
                    Tuning = table.Column<float>(type: "real", nullable: false),
                    AnalyzedAt = table.Column<DateTime>(type: "timestamp with time zone", nullable: false)
                },
                constraints: table =>
                {
                    table.PrimaryKey("PK_AnalysisResults", x => x.Id);
                    table.ForeignKey(
                        name: "FK_AnalysisResults_AudioFiles_AudioFileId",
                        column: x => x.AudioFileId,
                        principalTable: "AudioFiles",
                        principalColumn: "Id",
                        onDelete: ReferentialAction.Cascade);
                });

            migrationBuilder.CreateTable(
                name: "GenerationRequests",
                columns: table => new
                {
                    Id = table.Column<Guid>(type: "uuid", nullable: false),
                    AudioFileId = table.Column<Guid>(type: "uuid", nullable: false),
                    TargetStems = table.Column<int[]>(type: "integer[]", nullable: false),
                    Parameters_TargetBpm = table.Column<float>(type: "real", nullable: true),
                    Parameters_DurationSeconds = table.Column<float>(type: "real", nullable: false),
                    Parameters_Style = table.Column<string>(type: "text", nullable: true),
                    Parameters_ChordProgression = table.Column<List<string>>(type: "text[]", nullable: true),
                    Parameters_Prompt = table.Column<string>(type: "text", nullable: true),
                    Parameters_Temperature = table.Column<float>(type: "real", nullable: false),
                    Parameters_RandomSeed = table.Column<int>(type: "integer", nullable: true),
                    RequestedAt = table.Column<DateTime>(type: "timestamp with time zone", nullable: false),
                    CompletedAt = table.Column<DateTime>(type: "timestamp with time zone", nullable: true),
                    Status = table.Column<string>(type: "text", nullable: false),
                    ErrorMessage = table.Column<string>(type: "text", nullable: true)
                },
                constraints: table =>
                {
                    table.PrimaryKey("PK_GenerationRequests", x => x.Id);
                    table.ForeignKey(
                        name: "FK_GenerationRequests_AudioFiles_AudioFileId",
                        column: x => x.AudioFileId,
                        principalTable: "AudioFiles",
                        principalColumn: "Id",
                        onDelete: ReferentialAction.Cascade);
                });

            migrationBuilder.CreateTable(
                name: "JAMSAnnotations",
                columns: table => new
                {
                    Id = table.Column<Guid>(type: "uuid", nullable: false),
                    AudioFileId = table.Column<Guid>(type: "uuid", nullable: false),
                    JamsJson = table.Column<string>(type: "text", nullable: false),
                    BlobUri = table.Column<string>(type: "character varying(2000)", maxLength: 2000, nullable: false),
                    CreatedAt = table.Column<DateTime>(type: "timestamp with time zone", nullable: false)
                },
                constraints: table =>
                {
                    table.PrimaryKey("PK_JAMSAnnotations", x => x.Id);
                    table.ForeignKey(
                        name: "FK_JAMSAnnotations_AudioFiles_AudioFileId",
                        column: x => x.AudioFileId,
                        principalTable: "AudioFiles",
                        principalColumn: "Id",
                        onDelete: ReferentialAction.Cascade);
                });

            migrationBuilder.CreateTable(
                name: "Stems",
                columns: table => new
                {
                    Id = table.Column<Guid>(type: "uuid", nullable: false),
                    AudioFileId = table.Column<Guid>(type: "uuid", nullable: false),
                    Type = table.Column<string>(type: "text", nullable: false),
                    BlobUri = table.Column<string>(type: "character varying(2000)", maxLength: 2000, nullable: false),
                    DurationSeconds = table.Column<float>(type: "real", nullable: false),
                    SeparatedAt = table.Column<DateTime>(type: "timestamp with time zone", nullable: false),
                    SourceSeparationModel = table.Column<string>(type: "character varying(100)", maxLength: 100, nullable: false)
                },
                constraints: table =>
                {
                    table.PrimaryKey("PK_Stems", x => x.Id);
                    table.ForeignKey(
                        name: "FK_Stems_AudioFiles_AudioFileId",
                        column: x => x.AudioFileId,
                        principalTable: "AudioFiles",
                        principalColumn: "Id",
                        onDelete: ReferentialAction.Cascade);
                });

            migrationBuilder.CreateTable(
                name: "BeatAnnotation",
                columns: table => new
                {
                    Id = table.Column<Guid>(type: "uuid", nullable: false),
                    AnalysisResultId = table.Column<Guid>(type: "uuid", nullable: false),
                    Time = table.Column<float>(type: "real", nullable: false),
                    Position = table.Column<int>(type: "integer", nullable: false),
                    IsDownbeat = table.Column<bool>(type: "boolean", nullable: false)
                },
                constraints: table =>
                {
                    table.PrimaryKey("PK_BeatAnnotation", x => new { x.AnalysisResultId, x.Id });
                    table.ForeignKey(
                        name: "FK_BeatAnnotation_AnalysisResults_AnalysisResultId",
                        column: x => x.AnalysisResultId,
                        principalTable: "AnalysisResults",
                        principalColumn: "Id",
                        onDelete: ReferentialAction.Cascade);
                });

            migrationBuilder.CreateTable(
                name: "ChordAnnotation",
                columns: table => new
                {
                    Id = table.Column<Guid>(type: "uuid", nullable: false),
                    AnalysisResultId = table.Column<Guid>(type: "uuid", nullable: false),
                    StartTime = table.Column<float>(type: "real", nullable: false),
                    EndTime = table.Column<float>(type: "real", nullable: false),
                    Chord = table.Column<string>(type: "text", nullable: false),
                    Confidence = table.Column<float>(type: "real", nullable: false)
                },
                constraints: table =>
                {
                    table.PrimaryKey("PK_ChordAnnotation", x => new { x.AnalysisResultId, x.Id });
                    table.ForeignKey(
                        name: "FK_ChordAnnotation_AnalysisResults_AnalysisResultId",
                        column: x => x.AnalysisResultId,
                        principalTable: "AnalysisResults",
                        principalColumn: "Id",
                        onDelete: ReferentialAction.Cascade);
                });

            migrationBuilder.CreateTable(
                name: "Section",
                columns: table => new
                {
                    Id = table.Column<Guid>(type: "uuid", nullable: false),
                    AnalysisResultId = table.Column<Guid>(type: "uuid", nullable: false),
                    StartTime = table.Column<float>(type: "real", nullable: false),
                    EndTime = table.Column<float>(type: "real", nullable: false),
                    Label = table.Column<string>(type: "character varying(50)", maxLength: 50, nullable: false),
                    Confidence = table.Column<float>(type: "real", nullable: false)
                },
                constraints: table =>
                {
                    table.PrimaryKey("PK_Section", x => new { x.AnalysisResultId, x.Id });
                    table.ForeignKey(
                        name: "FK_Section_AnalysisResults_AnalysisResultId",
                        column: x => x.AnalysisResultId,
                        principalTable: "AnalysisResults",
                        principalColumn: "Id",
                        onDelete: ReferentialAction.Cascade);
                });

            migrationBuilder.CreateTable(
                name: "GeneratedStems",
                columns: table => new
                {
                    Id = table.Column<Guid>(type: "uuid", nullable: false),
                    GenerationRequestId = table.Column<Guid>(type: "uuid", nullable: false),
                    Type = table.Column<string>(type: "text", nullable: false),
                    BlobUri = table.Column<string>(type: "character varying(2000)", maxLength: 2000, nullable: false),
                    DurationSeconds = table.Column<float>(type: "real", nullable: false),
                    Format = table.Column<string>(type: "character varying(20)", maxLength: 20, nullable: false),
                    SampleRate = table.Column<int>(type: "integer", nullable: false),
                    BitDepth = table.Column<int>(type: "integer", nullable: false),
                    Channels = table.Column<int>(type: "integer", nullable: false),
                    GeneratedAt = table.Column<DateTime>(type: "timestamp with time zone", nullable: false),
                    Metadata_ModelName = table.Column<string>(type: "character varying(100)", maxLength: 100, nullable: false),
                    Metadata_ModelVersion = table.Column<string>(type: "character varying(50)", maxLength: 50, nullable: false),
                    Metadata_InferenceTimeSeconds = table.Column<float>(type: "real", nullable: false),
                    Metadata_RandomSeed = table.Column<int>(type: "integer", nullable: true),
                    Metadata_Conditioning = table.Column<string>(type: "text", nullable: false)
                },
                constraints: table =>
                {
                    table.PrimaryKey("PK_GeneratedStems", x => x.Id);
                    table.ForeignKey(
                        name: "FK_GeneratedStems_GenerationRequests_GenerationRequestId",
                        column: x => x.GenerationRequestId,
                        principalTable: "GenerationRequests",
                        principalColumn: "Id",
                        onDelete: ReferentialAction.Cascade);
                });

            migrationBuilder.CreateIndex(
                name: "IX_AnalysisResults_AnalyzedAt",
                table: "AnalysisResults",
                column: "AnalyzedAt");

            migrationBuilder.CreateIndex(
                name: "IX_AnalysisResults_AudioFileId",
                table: "AnalysisResults",
                column: "AudioFileId",
                unique: true);

            migrationBuilder.CreateIndex(
                name: "IX_AudioFiles_Status",
                table: "AudioFiles",
                column: "Status");

            migrationBuilder.CreateIndex(
                name: "IX_AudioFiles_UploadedAt",
                table: "AudioFiles",
                column: "UploadedAt");

            migrationBuilder.CreateIndex(
                name: "IX_GeneratedStems_GeneratedAt",
                table: "GeneratedStems",
                column: "GeneratedAt");

            migrationBuilder.CreateIndex(
                name: "IX_GeneratedStems_GenerationRequestId",
                table: "GeneratedStems",
                column: "GenerationRequestId",
                unique: true);

            migrationBuilder.CreateIndex(
                name: "IX_GenerationRequests_AudioFileId",
                table: "GenerationRequests",
                column: "AudioFileId");

            migrationBuilder.CreateIndex(
                name: "IX_GenerationRequests_RequestedAt",
                table: "GenerationRequests",
                column: "RequestedAt");

            migrationBuilder.CreateIndex(
                name: "IX_GenerationRequests_Status",
                table: "GenerationRequests",
                column: "Status");

            migrationBuilder.CreateIndex(
                name: "IX_JAMSAnnotations_AudioFileId",
                table: "JAMSAnnotations",
                column: "AudioFileId");

            migrationBuilder.CreateIndex(
                name: "IX_JAMSAnnotations_CreatedAt",
                table: "JAMSAnnotations",
                column: "CreatedAt");

            migrationBuilder.CreateIndex(
                name: "IX_Jobs_EntityId",
                table: "Jobs",
                column: "EntityId");

            migrationBuilder.CreateIndex(
                name: "IX_Jobs_StartedAt",
                table: "Jobs",
                column: "StartedAt");

            migrationBuilder.CreateIndex(
                name: "IX_Jobs_Status",
                table: "Jobs",
                column: "Status");

            migrationBuilder.CreateIndex(
                name: "IX_Stems_AudioFileId",
                table: "Stems",
                column: "AudioFileId");

            migrationBuilder.CreateIndex(
                name: "IX_Stems_SeparatedAt",
                table: "Stems",
                column: "SeparatedAt");

            migrationBuilder.CreateIndex(
                name: "IX_Stems_Type",
                table: "Stems",
                column: "Type");
        }

        /// <inheritdoc />
        protected override void Down(MigrationBuilder migrationBuilder)
        {
            migrationBuilder.DropTable(
                name: "BeatAnnotation");

            migrationBuilder.DropTable(
                name: "ChordAnnotation");

            migrationBuilder.DropTable(
                name: "GeneratedStems");

            migrationBuilder.DropTable(
                name: "JAMSAnnotations");

            migrationBuilder.DropTable(
                name: "Jobs");

            migrationBuilder.DropTable(
                name: "Section");

            migrationBuilder.DropTable(
                name: "Stems");

            migrationBuilder.DropTable(
                name: "GenerationRequests");

            migrationBuilder.DropTable(
                name: "AnalysisResults");

            migrationBuilder.DropTable(
                name: "AudioFiles");
        }
    }
}
