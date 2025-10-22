using System;
using Microsoft.EntityFrameworkCore.Migrations;

#nullable disable

namespace MusicPlatform.Api.Migrations
{
    /// <inheritdoc />
    public partial class AddTrainingSupport : Migration
    {
        /// <inheritdoc />
        protected override void Up(MigrationBuilder migrationBuilder)
        {
            migrationBuilder.CreateTable(
                name: "TrainingDatasets",
                columns: table => new
                {
                    Id = table.Column<Guid>(type: "uuid", nullable: false),
                    Name = table.Column<string>(type: "character varying(200)", maxLength: 200, nullable: false),
                    Description = table.Column<string>(type: "character varying(1000)", maxLength: 1000, nullable: true),
                    Status = table.Column<string>(type: "text", nullable: false),
                    CreatedAt = table.Column<DateTime>(type: "timestamp with time zone", nullable: false),
                    UpdatedAt = table.Column<DateTime>(type: "timestamp with time zone", nullable: false),
                    TotalDurationSeconds = table.Column<float>(type: "real", nullable: false),
                    StemCount = table.Column<int>(type: "integer", nullable: false),
                    Metadata = table.Column<string>(type: "text", nullable: false)
                },
                constraints: table =>
                {
                    table.PrimaryKey("PK_TrainingDatasets", x => x.Id);
                });

            migrationBuilder.CreateTable(
                name: "TrainedModels",
                columns: table => new
                {
                    Id = table.Column<Guid>(type: "uuid", nullable: false),
                    TrainingDatasetId = table.Column<Guid>(type: "uuid", nullable: false),
                    Name = table.Column<string>(type: "character varying(200)", maxLength: 200, nullable: false),
                    Description = table.Column<string>(type: "character varying(1000)", maxLength: 1000, nullable: true),
                    ModelPath = table.Column<string>(type: "character varying(2000)", maxLength: 2000, nullable: false),
                    ModelSizeBytes = table.Column<long>(type: "bigint", nullable: false),
                    BaseModel = table.Column<string>(type: "character varying(100)", maxLength: 100, nullable: false),
                    TrainingConfig = table.Column<string>(type: "text", nullable: false),
                    TrainingMetrics = table.Column<string>(type: "text", nullable: false),
                    Status = table.Column<string>(type: "text", nullable: false),
                    TrainingStartedAt = table.Column<DateTime>(type: "timestamp with time zone", nullable: true),
                    TrainingCompletedAt = table.Column<DateTime>(type: "timestamp with time zone", nullable: true),
                    CreatedAt = table.Column<DateTime>(type: "timestamp with time zone", nullable: false),
                    ErrorMessage = table.Column<string>(type: "character varying(2000)", maxLength: 2000, nullable: true),
                    UsageCount = table.Column<int>(type: "integer", nullable: false),
                    LastUsedAt = table.Column<DateTime>(type: "timestamp with time zone", nullable: true)
                },
                constraints: table =>
                {
                    table.PrimaryKey("PK_TrainedModels", x => x.Id);
                    table.ForeignKey(
                        name: "FK_TrainedModels_TrainingDatasets_TrainingDatasetId",
                        column: x => x.TrainingDatasetId,
                        principalTable: "TrainingDatasets",
                        principalColumn: "Id",
                        onDelete: ReferentialAction.Cascade);
                });

            migrationBuilder.CreateTable(
                name: "TrainingDatasetStems",
                columns: table => new
                {
                    Id = table.Column<Guid>(type: "uuid", nullable: false),
                    TrainingDatasetId = table.Column<Guid>(type: "uuid", nullable: false),
                    StemId = table.Column<Guid>(type: "uuid", nullable: false),
                    Weight = table.Column<float>(type: "real", nullable: false),
                    Order = table.Column<int>(type: "integer", nullable: false),
                    AddedAt = table.Column<DateTime>(type: "timestamp with time zone", nullable: false),
                    Notes = table.Column<string>(type: "character varying(500)", maxLength: 500, nullable: true)
                },
                constraints: table =>
                {
                    table.PrimaryKey("PK_TrainingDatasetStems", x => x.Id);
                    table.ForeignKey(
                        name: "FK_TrainingDatasetStems_Stems_StemId",
                        column: x => x.StemId,
                        principalTable: "Stems",
                        principalColumn: "Id",
                        onDelete: ReferentialAction.Restrict);
                    table.ForeignKey(
                        name: "FK_TrainingDatasetStems_TrainingDatasets_TrainingDatasetId",
                        column: x => x.TrainingDatasetId,
                        principalTable: "TrainingDatasets",
                        principalColumn: "Id",
                        onDelete: ReferentialAction.Cascade);
                });

            migrationBuilder.CreateIndex(
                name: "IX_TrainedModels_CreatedAt",
                table: "TrainedModels",
                column: "CreatedAt");

            migrationBuilder.CreateIndex(
                name: "IX_TrainedModels_LastUsedAt",
                table: "TrainedModels",
                column: "LastUsedAt");

            migrationBuilder.CreateIndex(
                name: "IX_TrainedModels_Status",
                table: "TrainedModels",
                column: "Status");

            migrationBuilder.CreateIndex(
                name: "IX_TrainedModels_TrainingDatasetId",
                table: "TrainedModels",
                column: "TrainingDatasetId");

            migrationBuilder.CreateIndex(
                name: "IX_TrainingDatasets_CreatedAt",
                table: "TrainingDatasets",
                column: "CreatedAt");

            migrationBuilder.CreateIndex(
                name: "IX_TrainingDatasets_Status",
                table: "TrainingDatasets",
                column: "Status");

            migrationBuilder.CreateIndex(
                name: "IX_TrainingDatasetStems_Order",
                table: "TrainingDatasetStems",
                column: "Order");

            migrationBuilder.CreateIndex(
                name: "IX_TrainingDatasetStems_StemId",
                table: "TrainingDatasetStems",
                column: "StemId");

            migrationBuilder.CreateIndex(
                name: "IX_TrainingDatasetStems_TrainingDatasetId",
                table: "TrainingDatasetStems",
                column: "TrainingDatasetId");
        }

        /// <inheritdoc />
        protected override void Down(MigrationBuilder migrationBuilder)
        {
            migrationBuilder.DropTable(
                name: "TrainedModels");

            migrationBuilder.DropTable(
                name: "TrainingDatasetStems");

            migrationBuilder.DropTable(
                name: "TrainingDatasets");
        }
    }
}
