# Build stage
FROM mcr.microsoft.com/dotnet/sdk:9.0 AS build
WORKDIR /src

# Copy csproj files and restore dependencies
COPY ["src/MusicPlatform.Api/MusicPlatform.Api.csproj", "MusicPlatform.Api/"]
COPY ["src/MusicPlatform.Domain/MusicPlatform.Domain.csproj", "MusicPlatform.Domain/"]
COPY ["src/MusicPlatform.Infrastructure/MusicPlatform.Infrastructure.csproj", "MusicPlatform.Infrastructure/"]
COPY ["Directory.Build.props", "./"]

RUN dotnet restore "MusicPlatform.Api/MusicPlatform.Api.csproj"

# Copy all source files and build
COPY src/ .
WORKDIR "/src/MusicPlatform.Api"
RUN dotnet build "MusicPlatform.Api.csproj" -c Release -o /app/build

# Publish stage
FROM build AS publish
RUN dotnet publish "MusicPlatform.Api.csproj" -c Release -o /app/publish /p:UseAppHost=false

# Runtime stage
FROM mcr.microsoft.com/dotnet/aspnet:9.0 AS final
WORKDIR /app
EXPOSE 8080
COPY --from=publish /app/publish .
ENTRYPOINT ["dotnet", "MusicPlatform.Api.dll"]
