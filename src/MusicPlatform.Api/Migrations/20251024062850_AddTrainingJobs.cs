using System;
using Microsoft.EntityFrameworkCore.Migrations;

#nullable disable

namespace MusicPlatform.Api.Migrations
{
    /// <inheritdoc />
    public partial class AddTrainingJobs : Migration
    {
        /// <inheritdoc />
        protected override void Up(MigrationBuilder migrationBuilder)
        {
            migrationBuilder.CreateTable(
                name: "TrainingJobs",
                columns: table => new
                {
                    Id = table.Column<Guid>(type: "uuid", nullable: false),
                    TrainingDatasetId = table.Column<Guid>(type: "uuid", nullable: false),
                    ModelName = table.Column<string>(type: "character varying(200)", maxLength: 200, nullable: false),
                    BaseModel = table.Column<string>(type: "character varying(100)", maxLength: 100, nullable: false),
                    Status = table.Column<string>(type: "text", nullable: false),
                    Hyperparameters = table.Column<string>(type: "text", nullable: false),
                    Progress = table.Column<float>(type: "real", nullable: false),
                    CurrentEpoch = table.Column<int>(type: "integer", nullable: false),
                    TotalEpochs = table.Column<int>(type: "integer", nullable: false),
                    CurrentLoss = table.Column<float>(type: "real", nullable: true),
                    ErrorMessage = table.Column<string>(type: "character varying(2000)", maxLength: 2000, nullable: true),
                    CreatedAt = table.Column<DateTime>(type: "timestamp with time zone", nullable: false),
                    StartedAt = table.Column<DateTime>(type: "timestamp with time zone", nullable: true),
                    CompletedAt = table.Column<DateTime>(type: "timestamp with time zone", nullable: true),
                    DurationSeconds = table.Column<float>(type: "real", nullable: true),
                    TrainedModelId = table.Column<Guid>(type: "uuid", nullable: true),
                    Metadata = table.Column<string>(type: "text", nullable: false)
                },
                constraints: table =>
                {
                    table.PrimaryKey("PK_TrainingJobs", x => x.Id);
                    table.ForeignKey(
                        name: "FK_TrainingJobs_TrainedModels_TrainedModelId",
                        column: x => x.TrainedModelId,
                        principalTable: "TrainedModels",
                        principalColumn: "Id",
                        onDelete: ReferentialAction.SetNull);
                    table.ForeignKey(
                        name: "FK_TrainingJobs_TrainingDatasets_TrainingDatasetId",
                        column: x => x.TrainingDatasetId,
                        principalTable: "TrainingDatasets",
                        principalColumn: "Id",
                        onDelete: ReferentialAction.Cascade);
                });

            migrationBuilder.CreateIndex(
                name: "IX_TrainingJobs_CompletedAt",
                table: "TrainingJobs",
                column: "CompletedAt");

            migrationBuilder.CreateIndex(
                name: "IX_TrainingJobs_CreatedAt",
                table: "TrainingJobs",
                column: "CreatedAt");

            migrationBuilder.CreateIndex(
                name: "IX_TrainingJobs_StartedAt",
                table: "TrainingJobs",
                column: "StartedAt");

            migrationBuilder.CreateIndex(
                name: "IX_TrainingJobs_Status",
                table: "TrainingJobs",
                column: "Status");

            migrationBuilder.CreateIndex(
                name: "IX_TrainingJobs_TrainedModelId",
                table: "TrainingJobs",
                column: "TrainedModelId");

            migrationBuilder.CreateIndex(
                name: "IX_TrainingJobs_TrainingDatasetId",
                table: "TrainingJobs",
                column: "TrainingDatasetId");
        }

        /// <inheritdoc />
        protected override void Down(MigrationBuilder migrationBuilder)
        {
            migrationBuilder.DropTable(
                name: "TrainingJobs");
        }
    }
}
